"""
The one way a line gets added to a document: type, item, quantity, unit
price, Add — in a single line above the list it adds to.

Shared by the sale and the purchase because adding a line is the same act
either way, and the two forms sit side by side in the same session: a
shopkeeper who learns one has learnt the other. What differs between them
is not how a line is picked but what may be picked — a sale cannot sell
stock that isn't there — and that stays with the dialog, which is where
the rule lives.

The row reports rather than decides. It emits `added` for a choice that
is complete, `rejected` for one that is not, and leaves itself alone
afterwards: the caller resets it once the line has actually been taken,
so a refused line keeps what was typed instead of clearing it.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget

from app.domain.enums.item_type import ItemType
from app.presentation.formatting import card_label
from app.presentation.widgets.document_lines import ZERO, parse_amount
from app.presentation.widgets.form_field import field
from app.presentation.widgets.item_type_combo import ItemTypeCombo
from app.presentation.widgets.modern_spinbox import ModernSpinBox

_NONE_AVAILABLE = "— none available —"
_UNCAPPED = 1_000_000


@dataclass(frozen=True, slots=True)
class PickedItem:
    """A complete choice, ready to become a document line."""

    item_type: ItemType
    item_id: int
    label: str
    quantity: int
    unit_price: Decimal


class ItemPickerRow(QWidget):
    added = Signal(object)  # PickedItem
    rejected = Signal(str)  # why nothing was added
    itemChanged = Signal(object, int)  # ItemType, item id — or (type, 0) for none

    def __init__(
        self,
        cards: list,
        inventory_items: list,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cards = cards
        self._inventory_items = inventory_items

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self._kind = ItemTypeCombo()
        self._kind.currentIndexChanged.connect(self._on_kind_changed)

        self._item = QComboBox()
        self._item.setMinimumWidth(220)
        self._item.currentIndexChanged.connect(self._on_item_changed)

        self._quantity = ModernSpinBox()
        self._quantity.setRange(1, _UNCAPPED)
        self._quantity.setValue(1)

        self._unit_price = QLineEdit()
        self._unit_price.setPlaceholderText("0.00")
        self._unit_price.setMaximumWidth(120)
        # Enter at the end of the row does what the button beside it does:
        # the price is the last thing typed, every time.
        self._unit_price.returnPressed.connect(self.submit)

        add_button = QPushButton("Add item")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self.submit)

        row.addLayout(field("Type", self._kind))
        row.addLayout(field("Item", self._item), 1)
        row.addLayout(field("Quantity", self._quantity))
        row.addLayout(field("Unit price", self._unit_price))
        row.addLayout(field("", add_button))

        self._on_kind_changed(0)

    # ---------------- state ----------------

    def _on_kind_changed(self, _index: int) -> None:
        is_card = self._kind.is_card
        rows = self._cards if is_card else self._inventory_items
        self._item.clear()
        if not rows:
            self._item.addItem(_NONE_AVAILABLE, None)
        for row in rows:
            self._item.addItem(card_label(row) if is_card else row.name, row.id)

    def _on_item_changed(self, _index: int = 0) -> None:
        item_id = self._item.currentData()
        if item_id is not None:
            self.itemChanged.emit(self._kind.selected_type(), item_id)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # The row fills its item list while it is being constructed, which
        # is before the dialog has had a chance to connect to it — so the
        # first selection would otherwise be the one nobody was told
        # about, and a sale would open with its quantity uncapped.
        self._on_item_changed()

    def set_quantity_limit(self, limit: int | None) -> None:
        """Cap what can be typed into the quantity, for a document that has
        one — a sale cannot be for more than is on the shelf.

        Refusing the number as it is typed beats accepting it and then
        explaining, and it is the same cap the use case would apply.
        """
        self._quantity.setRange(1, max(1, limit) if limit is not None else _UNCAPPED)

    def reset(self) -> None:
        """Ready for the next line. Called once the last one was taken."""
        self._unit_price.clear()
        self._quantity.setValue(1)
        self._item.setFocus()

    # ---------------- adding ----------------

    def submit(self) -> None:
        item_id = self._item.currentData()
        if item_id is None:
            self.rejected.emit("Choose an item to add.")
            self._item.setFocus()
            return

        unit_price = parse_amount(self._unit_price.text())
        if unit_price is None or unit_price < ZERO:
            self.rejected.emit("Enter a unit price for this item.")
            self._unit_price.setFocus()
            return

        self.added.emit(
            PickedItem(
                item_type=self._kind.selected_type(),
                item_id=item_id,
                label=self._item.currentText(),
                quantity=self._quantity.value(),
                unit_price=unit_price,
            )
        )
