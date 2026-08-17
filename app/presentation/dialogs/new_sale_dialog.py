"""
New sale: invoice and customer, what was sold, what was paid.

The shape of the form comes from `DocumentDialog` — the same one the
purchase dialog uses, so a sale and a purchase are recorded the same way
round, down to the row a line is picked in. What a sale differs by is
here: the invoice and customer fields, and the one rule a purchase has no
equivalent of — you cannot sell stock you do not have.
"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QWidget

from app.application.dto.commands import CreateSaleCommand, SaleItemCommand, SalePaymentCommand
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.document_dialog import DocumentDialog, step_panel
from app.presentation.item_types import item_name
from app.presentation.widgets.document_lines import DocumentTotals
from app.presentation.widgets.form_field import field
from app.presentation.widgets.input_validation import ZERO
from app.presentation.widgets.item_picker_row import ItemPickerRow, PickedItem
from app.presentation.widgets.searchable_combo import SearchableComboBox
from app.shared.datetimes import now_pkt

_WALK_IN = "Walk-in customer"


def _new_invoice_number() -> str:
    return f"INV-{now_pkt():%y%m%d%H%M%S}"


def unsellable_reason(product, label: str) -> str | None:
    """Why this item cannot go on an invoice today, or None if it can.

    Mirrors CreateSaleUseCase, which refuses to sell anything at or below
    its minimum stock. Said in one place because it is said at two moments
    — the moment the item is picked and the moment it is added — and the
    same item must not be out of stock in one of them and fine in the
    other.
    """
    if product.current_stock <= 0:
        return (
            f"'{label}' is out of stock. Record a purchase to bring it back "
            "in before selling it."
        )
    if product.current_stock <= product.minimum_stock:
        return (
            f"'{label}' is down to its minimum ({product.current_stock} left). "
            "Record a purchase to bring it back above its minimum before "
            "selling it."
        )
    return None


class NewSaleDialog(DocumentDialog):
    def __init__(
        self,
        view_model,
        *,
        customers: list,
        payment_methods: list,
        catalogues: dict[ItemType, list],
        current_user_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        # Set before super(), which calls the build hooks below.
        self._customers = customers
        self._catalogues = catalogues
        # The record behind everything the picker has offered, so the
        # stock rules below can be answered without going back for it.
        #
        # A cache, not a catalogue: the picker searches, and every batch it
        # is given passes through here first. So an id it can return is an
        # id this holds — which is the whole of why the out-of-stock rule
        # still holds without the dialog loading the shop's whole list.
        self._products: dict[tuple[ItemType, int], object] = {}
        self._remember(catalogues)

        super().__init__(
            view_model,
            title="New sale",
            subtitle="Choose what was sold, set quantities, then record the payment.",
            submit_label="Record sale",
            items_title="What was sold",
            empty_lines_message="Nothing added yet — choose an item above.",
            payment_methods=payment_methods,
            current_user_id=current_user_id,
            parent=parent,
        )

        # The view model outlives this dialog, so both are let go of again
        # in `done()` — see `DocumentDialog.listen`.
        self.listen(view_model.catalogueSearched, self._on_catalogue_searched)
        self.listen(view_model.partiesSearched, self._on_parties_searched)
        self._customer.searchRequested.connect(view_model.search_parties)

    # ---------------- step 1: invoice ----------------

    def build_identity_step(self) -> QFrame:
        panel, layout = step_panel("1", "Invoice and customer")

        row = QHBoxLayout()
        row.setSpacing(12)

        self._invoice_no = QLineEdit(_new_invoice_number())
        # Searched rather than scrolled, for the same reason the item is:
        # a shop's customer list is as long as the shop is old.
        self._customer = SearchableComboBox()
        self._customer.setToolTip("Type any part of a customer's name to find them")
        self._customer.set_placeholder_item(_WALK_IN, None)
        self._customer.set_options([(c.name, c.id) for c in self._customers])

        row.addLayout(field("Invoice number", self._invoice_no), 1)
        row.addLayout(field("Customer", self._customer), 1)
        layout.addLayout(row)
        return panel

    # ---------------- step 2: picker ----------------

    def build_picker(self) -> QWidget:
        self._picker = ItemPickerRow(
            self._catalogues, search=self._view_model.search_catalogue
        )
        self._picker.added.connect(self._add_line)
        self._picker.rejected.connect(self.warn)
        self._picker.itemChanged.connect(self._on_item_changed)
        self._picker.itemChosen.connect(self._on_item_chosen)
        return self._picker

    def _on_catalogue_searched(self, item_type: ItemType, term: str, records: list) -> None:
        # Into the cache before the picker can offer any of them, so the
        # stock rules can answer for anything it becomes possible to pick.
        self._remember({item_type: records})
        self._picker.set_options(item_type, records, term)

    def _on_parties_searched(self, term: str, customers: list) -> None:
        self._customer.set_options([(c.name, c.id) for c in customers], term=term)

    def _remember(self, catalogues: dict) -> None:
        self._products.update(
            {
                (ItemType(item_type), record.id): record
                for item_type, records in catalogues.items()
                for record in records
            }
        )

    def _on_item_changed(self, item_type: ItemType, item_id: int) -> None:
        # The quantity can never exceed what is on the shelf, so the field
        # stops there rather than letting a number be typed that the sale
        # would then refuse.
        self._picker.set_quantity_limit(self.available_stock(item_type, item_id))

    def _on_item_chosen(self, item_type: ItemType, item_id: int) -> None:
        """Say an item is out of stock the moment it is picked.

        Only for the item that has actually run out, and only once it has
        been chosen: a warning about the row the form merely opened on, or
        about an item that is merely low, is one nobody asked for.
        """
        product = self._products.get((item_type, item_id))
        if product is not None and product.current_stock <= 0:
            self.warn(unsellable_reason(product, item_name(item_type, product)))

    def _add_line(self, picked: PickedItem) -> None:
        product = self._products.get((picked.item_type, picked.item_id))
        if product is None:
            self.warn("That item is no longer in the catalogue. Refresh and try again.")
            return

        # Hearing it here beats hearing it after the whole invoice has
        # been built.
        refusal = unsellable_reason(product, picked.label)
        if refusal is not None:
            self.warn(refusal)
            return

        already = self.line_for(picked.item_type, picked.item_id)
        on_hand = product.current_stock
        wanted = picked.quantity + (already.quantity if already is not None else 0)
        if wanted > on_hand:
            self.warn(
                f"Only {on_hand} of '{picked.label}' in stock, and this invoice "
                f"already has {already.quantity if already else 0}."
            )
            return

        self.add_line(
            item_type=picked.item_type,
            item_id=picked.item_id,
            label=picked.label,
            quantity=picked.quantity,
            unit_price=picked.unit_price,
        )
        self._picker.reset()

    def available_stock(self, item_type: ItemType, item_id: int) -> int | None:
        product = self._products.get((item_type, item_id))
        return product.current_stock if product is not None else None

    # ---------------- submit ----------------

    def validate(self) -> bool:
        if not self._invoice_no.text().strip():
            self.warn("Invoice number is required.")
            self._invoice_no.setFocus()
            return False
        return True

    def build_command(self, totals: DocumentTotals) -> CreateSaleCommand:
        payments = []
        if totals.paid > ZERO:
            payments.append(
                SalePaymentCommand(
                    amount=totals.paid,
                    payment_method_id=self._totals.payment_method_id,
                    received_by_user_id=self._current_user_id,
                )
            )

        return CreateSaleCommand(
            invoice_no=self._invoice_no.text().strip(),
            customer_id=self._customer.currentData(),
            discount_amount=totals.discount,
            items=[
                SaleItemCommand(
                    item_type=line.item_type,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    inventory_item_id=line.item_id,
                )
                for line in self.lines
            ],
            payments=payments,
        )