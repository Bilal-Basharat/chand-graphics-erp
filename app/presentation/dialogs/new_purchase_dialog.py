"""
New purchase: supplier and reference, what was bought, what was paid.

Everything about the shape of this form — the numbered steps, the line
list, the totals, the submit lifecycle — lives in `DocumentDialog`,
because the sale dialog is the same form in the opposite direction. What
is left here is what a purchase actually differs by: the supplier and
reference fields, a dropdown picker, and the purchase command.

Purchases raise stock, so quantities are unconstrained: unlike a sale,
there is no "not enough stock" case to guard against.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QWidget,
)

from app.application.dto.commands import (
    CreatePurchaseCommand,
    PurchaseItemCommand,
    PurchasePaymentCommand,
)
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.document_dialog import DocumentDialog, step_panel
from app.presentation.widgets.document_lines import DocumentTotals
from app.presentation.widgets.form_field import field
from app.presentation.widgets.input_validation import ZERO
from app.presentation.widgets.item_picker_row import ItemPickerRow, PickedItem
from app.presentation.widgets.searchable_combo import SearchableComboBox
from app.shared.datetimes import now_pkt

_CHOOSE_SUPPLIER = "— Choose a supplier —"


def _new_purchase_number() -> str:
    return f"PUR-{now_pkt():%y%m%d%H%M%S}"


class NewPurchaseDialog(DocumentDialog):
    def __init__(
        self,
        view_model,
        *,
        suppliers: list,
        payment_methods: list,
        catalogues: dict[ItemType, list],
        current_user_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        # Set before super(), which calls the build hooks below.
        self._suppliers = suppliers
        self._catalogues = catalogues
        # The records the picker has offered, kept for their unit —
        # see `_remember`.
        self._items: dict[int, object] = {}
        self._remember(catalogues)

        super().__init__(
            view_model,
            title="New purchase",
            subtitle="Record stock bought in, and anything paid for it now.",
            submit_label="Record purchase",
            items_title="What was bought",
            empty_lines_message="Nothing added yet — choose an item above.",
            payment_methods=payment_methods,
            current_user_id=current_user_id,
            parent=parent,
        )

        # Let go of again in `done()` — the view model outlives this.
        self.listen(view_model.catalogueSearched, self._on_catalogue_searched)
        self.listen(view_model.unitsLoaded, self._on_units_loaded)
        self.listen(view_model.partiesSearched, self._on_parties_searched)
        self._supplier.searchRequested.connect(view_model.search_parties)

    # ---------------- step 1: supplier ----------------

    def build_identity_step(self) -> QFrame:
        panel, layout = step_panel("1", "Supplier and reference")

        row = QHBoxLayout()
        row.setSpacing(12)

        self._purchase_no = QLineEdit(_new_purchase_number())
        # Searched rather than scrolled, for the same reason the item is.
        self._supplier = SearchableComboBox()
        self._supplier.setToolTip("Type any part of a supplier's name to find them")
        # A prompt, not a choice: stock comes from someone, and a purchase
        # that doesn't say who leaves its payments owed to nobody. Kept
        # through every refill, or a search would quietly answer it.
        self._supplier.set_placeholder_item(_CHOOSE_SUPPLIER, None)
        self._supplier.set_options([(s.name, s.id) for s in self._suppliers])
        self._reference = QLineEdit()
        self._reference.setPlaceholderText("Supplier invoice or bill number")

        row.addLayout(field("Purchase number", self._purchase_no), 1)
        row.addLayout(field("Supplier", self._supplier), 1)
        row.addLayout(field("Reference", self._reference), 1)
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
        return self._picker

    def _on_catalogue_searched(self, item_type, term: str, records: list) -> None:
        self._remember({item_type: records})
        self._picker.set_options(item_type, records, term)

    def _remember(self, catalogues: dict) -> None:
        """Keep the records the picker has offered.

        Only for their unit: a purchase has no stock rule to answer, but
        the quantity box still has to say what it is counting in.
        """
        self._items.update(
            {record.id: record for records in catalogues.values() for record in records}
        )

    def _on_item_changed(self, item_type, item_id: int) -> None:
        item = self._items.get(item_id)
        self._picker.set_base_unit(getattr(item, "unit", None))
        self._picker.set_units(())
        self._view_model.load_units(item_type, item_id)

    def _on_units_loaded(self, _item_type, item_id: int, units: list) -> None:
        # The answer arrives off the UI thread; by then the picker may
        # have moved on — see the sale dialog.
        if self._picker.selected_id() == item_id:
            self._picker.set_units(units)

    def _on_parties_searched(self, term: str, suppliers: list) -> None:
        self._supplier.set_options([(s.name, s.id) for s in suppliers], term=term)

    def _add_line(self, picked: PickedItem) -> None:
        # Buying raises stock, so there is nothing to refuse: every
        # complete choice becomes a line.
        self.add_line(
            item_type=picked.item_type,
            item_id=picked.item_id,
            label=picked.label,
            quantity=picked.quantity,
            unit_price=picked.unit_price,
            uom_id=picked.uom_id,
            unit_label=picked.unit_label,
            base_quantity=picked.base_quantity,
        )
        self._picker.reset()

    # ---------------- submit ----------------

    def validate(self) -> bool:
        if not self._purchase_no.text().strip():
            self.warn("Purchase number is required.")
            self._purchase_no.setFocus()
            return False
        if self._supplier.currentData() is None:
            self.warn(
                "Choose the supplier this stock was bought from."
                if self._suppliers
                else "Add a supplier first — every purchase is recorded against one."
            )
            self._supplier.setFocus()
            return False
        return True

    def build_command(self, totals: DocumentTotals) -> CreatePurchaseCommand:
        payments = []
        if totals.paid > ZERO:
            payments.append(
                PurchasePaymentCommand(
                    amount=totals.paid,
                    payment_method_id=self._totals.payment_method_id,
                    paid_by_user_id=self._current_user_id,
                )
            )

        return CreatePurchaseCommand(
            purchase_no=self._purchase_no.text().strip(),
            supplier_id=self._supplier.currentData(),
            reference_no=self._reference.text().strip() or None,
            discount_amount=totals.discount,
            items=[
                PurchaseItemCommand(
                    item_type=line.item_type,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    inventory_item_id=line.item_id,
                    uom_id=line.uom_id,
                )
                for line in self.lines
            ],
            payments=payments,
        )