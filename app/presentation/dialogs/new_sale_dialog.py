"""
New sale: invoice and customer, what was sold, what was paid.

The shape of the form comes from `DocumentDialog` — the same one the
purchase dialog uses, so a sale and a purchase are recorded the same way
round. What a sale differs by is here: the invoice and customer fields, a
catalogue you pick from by recognising the product, and the one rule a
purchase has no equivalent of — you cannot sell stock you do not have.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLineEdit, QWidget

from app.application.dto.commands import CreateSaleCommand, SaleItemCommand, SalePaymentCommand
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.document_dialog import DocumentDialog, field, step_panel
from app.presentation.dialogs.line_item_dialog import LineItemDialog
from app.presentation.widgets.document_lines import ZERO, DocumentTotals
from app.presentation.widgets.product_picker import Product, ProductPicker

_WALK_IN = "Walk-in customer"


def _new_invoice_number() -> str:
    return f"INV-{datetime.now():%y%m%d%H%M%S}"


class NewSaleDialog(DocumentDialog):
    def __init__(
        self,
        view_model,
        *,
        customers: list,
        payment_methods: list,
        cards: list,
        inventory_items: list,
        current_user_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        # Set before super(), which calls the build hooks below.
        self._customers = customers
        self._cards = cards
        self._inventory_items = inventory_items
        self._stock = {
            (ItemType.CARD, card.id): card.current_stock for card in cards
        } | {(ItemType.INVENTORY_ITEM, item.id): item.current_stock for item in inventory_items}

        super().__init__(
            view_model,
            title="New sale",
            subtitle="Pick products, set quantities, then record the payment.",
            submit_label="Record sale",
            items_title="What was sold",
            empty_lines_message="Nothing added yet — pick a product above.",
            payment_methods=payment_methods,
            current_user_id=current_user_id,
            parent=parent,
        )

    # ---------------- step 1: invoice ----------------

    def build_identity_step(self) -> QFrame:
        panel, layout = step_panel("1", "Invoice and customer")

        row = QHBoxLayout()
        row.setSpacing(12)

        self._invoice_no = QLineEdit(_new_invoice_number())
        self._customer = QComboBox()
        self._customer.addItem(_WALK_IN, None)
        for customer in self._customers:
            self._customer.addItem(customer.name, customer.id)

        row.addLayout(field("Invoice number", self._invoice_no), 1)
        row.addLayout(field("Customer", self._customer), 1)
        layout.addLayout(row)
        return panel

    # ---------------- step 2: picker ----------------

    def build_picker(self) -> QWidget:
        picker = ProductPicker(self._cards, self._inventory_items)
        picker.picked.connect(self._pick)
        return picker

    def _pick(self, product: Product) -> None:
        if not product.sellable:
            self.warn(
                f"'{product.label}' is {product.blocked_reason.lower()}. "
                "Record a purchase to bring stock back above its minimum."
            )
            return

        existing = self.line_for(product.item_type, product.id)
        dialog = LineItemDialog(
            item_label=product.label,
            title="Add to sale" if existing is None else "Update line",
            submit_label="Add to sale" if existing is None else "Update line",
            quantity=existing.quantity + 1 if existing else 1,
            unit_price=existing.unit_price if existing else None,
            available_stock=product.current_stock,
            parent=self,
        )
        dialog.exec()
        entered = dialog.line()
        if entered is None:
            return
        quantity, unit_price = entered

        if existing is not None:
            # The dialog opened showing the line's current quantity, so what
            # comes back is the new total for it, not an amount to add.
            existing.quantity = quantity
            existing.unit_price = unit_price
            self._render_lines()
            return

        self.add_line(
            item_type=product.item_type,
            item_id=product.id,
            label=product.label,
            quantity=quantity,
            unit_price=unit_price,
        )

    def available_stock(self, item_type: ItemType, item_id: int) -> int | None:
        return self._stock.get((item_type, item_id))

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
                    card_id=line.item_id if line.item_type is ItemType.CARD else None,
                    inventory_item_id=None if line.item_type is ItemType.CARD else line.item_id,
                )
                for line in self.lines
            ],
            payments=payments,
        )
