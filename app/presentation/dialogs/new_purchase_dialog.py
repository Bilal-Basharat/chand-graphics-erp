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

from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.application.dto.commands import (
    CreatePurchaseCommand,
    PurchaseItemCommand,
    PurchasePaymentCommand,
)
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.document_dialog import DocumentDialog, field, step_panel
from app.presentation.formatting import card_label
from app.presentation.widgets.document_lines import ZERO, DocumentTotals, parse_amount
from app.presentation.widgets.item_type_combo import ItemTypeCombo
from app.presentation.widgets.modern_spinbox import ModernSpinBox
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
        cards: list,
        inventory_items: list,
        current_user_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        # Set before super(), which calls the build hooks below.
        self._suppliers = suppliers
        self._cards = cards
        self._inventory_items = inventory_items

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

        self._on_kind_changed(0)

    # ---------------- step 1: supplier ----------------

    def build_identity_step(self) -> QFrame:
        panel, layout = step_panel("1", "Supplier and reference")

        row = QHBoxLayout()
        row.setSpacing(12)

        self._purchase_no = QLineEdit(_new_purchase_number())
        self._supplier = QComboBox()
        # A prompt, not a choice: stock comes from someone, and a purchase
        # that doesn't say who leaves its payments owed to nobody.
        self._supplier.addItem(_CHOOSE_SUPPLIER, None)
        for supplier in self._suppliers:
            self._supplier.addItem(supplier.name, supplier.id)
        self._reference = QLineEdit()
        self._reference.setPlaceholderText("Supplier invoice or bill number")

        row.addLayout(field("Purchase number", self._purchase_no), 1)
        row.addLayout(field("Supplier", self._supplier), 1)
        row.addLayout(field("Reference", self._reference), 1)
        layout.addLayout(row)
        return panel

    # ---------------- step 2: picker ----------------

    def build_picker(self) -> QWidget:
        picker = QWidget()
        row = QHBoxLayout(picker)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self._kind = ItemTypeCombo()
        self._kind.currentIndexChanged.connect(self._on_kind_changed)

        self._item = QComboBox()
        self._item.setMinimumWidth(220)

        self._quantity = ModernSpinBox()
        self._quantity.setRange(1, 1_000_000)
        self._quantity.setValue(1)

        self._unit_price = QLineEdit()
        self._unit_price.setPlaceholderText("0.00")
        self._unit_price.setMaximumWidth(120)
        self._unit_price.returnPressed.connect(self._add_line)

        add_button = QPushButton("Add item")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self._add_line)

        row.addLayout(field("Type", self._kind))
        row.addLayout(field("Item", self._item), 1)
        row.addLayout(field("Quantity", self._quantity))
        row.addLayout(field("Unit price", self._unit_price))
        row.addLayout(field("", add_button))
        return picker

    def _on_kind_changed(self, _index: int) -> None:
        is_card = self._kind.is_card
        rows = self._cards if is_card else self._inventory_items
        self._item.clear()
        if not rows:
            self._item.addItem("— none available —", None)
        for row in rows:
            self._item.addItem(card_label(row) if is_card else row.name, row.id)

    def _add_line(self) -> None:
        item_id = self._item.currentData()
        if item_id is None:
            self.warn("Choose an item to add.")
            return

        unit_price = parse_amount(self._unit_price.text())
        if unit_price is None or unit_price < ZERO:
            self.warn("Enter the unit price paid for this item.")
            self._unit_price.setFocus()
            return

        self.add_line(
            item_type=self._kind.selected_type(),
            item_id=item_id,
            label=self._item.currentText(),
            quantity=self._quantity.value(),
            unit_price=unit_price,
        )

        self._unit_price.clear()
        self._quantity.setValue(1)
        self._item.setFocus()

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
                    card_id=line.item_id if line.item_type is ItemType.CARD else None,
                    inventory_item_id=None if line.item_type is ItemType.CARD else line.item_id,
                )
                for line in self.lines
            ],
            payments=payments,
        )
