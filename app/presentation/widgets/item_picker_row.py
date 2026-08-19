"""
The one way a line gets added to a document: type, item, quantity, unit
price, Add — in a single line above the list it adds to.

Shared by the sale and the purchase because adding a line is the same act
either way, and the two forms sit side by side in the same session: a
shopkeeper who learns one has learnt the other. What differs between them
is not how a line is picked but what may be picked — a sale cannot sell
stock that isn't there — and that stays with the dialog, which is where
the rule lives.

The item is searched rather than scrolled for — see `searchable_combo.py`
— because the list is a whole shop's catalogue and the item being sold is
one name in it.

The row reports rather than decides. It emits `added` for a choice that
is complete, `rejected` for one that is not, and leaves itself alone
afterwards: the caller resets it once the line has actually been taken,
so a refused line keeps what was typed instead of clearing it.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from app.domain.enums.item_type import ItemType
from app.presentation.widgets.form_field import field
from app.presentation.widgets.item_search_field import ItemDelegate, ItemSearchField
from app.presentation.widgets.input_validation import MoneyInput, parse_amount
from app.presentation.widgets.modern_spinbox import ModernSpinBox

__all__ = ["ItemDelegate", "ItemPickerRow", "PickedItem"]

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
    itemChanged = Signal(object, int)  # ItemType, item id — whatever is selected now
    itemChosen = Signal(object, int)  # ItemType, item id — and the user chose it

    def __init__(
        self,
        catalogues: dict[ItemType, list],
        *,
        search: Callable[[ItemType, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """`catalogues` is what to offer before anything is typed — the
        first page of each kind, not the whole of it.

        With a `search` callback the row asks for matches as it is typed
        into, and answers arrive back through `set_options`. Without one it
        filters what it was handed, which is right for a list short enough
        to hand over whole.
        """
        super().__init__(parent)
        self._catalogues = catalogues
        self._search = search

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        # Which item, asked the one way every stock screen asks it.
        self._picker = ItemSearchField()
        self._picker.kindChanged.connect(self._on_kind_changed)
        self._picker.itemChanged.connect(self._on_item_changed)
        self._picker.itemChosen.connect(self.itemChosen)
        if search is not None:
            self._picker.searchRequested.connect(search)

        # The tests and this row both reach the two boxes directly; they
        # are the field's, and named here so neither has to say so.
        self._kind = self._picker.kind
        self._item = self._picker.item

        self._quantity = ModernSpinBox()
        self._quantity.setRange(1, _UNCAPPED)
        self._quantity.setValue(1)

        self._unit_price = MoneyInput()
        self._unit_price.setMaximumWidth(120)
        # Enter at the end of the row does what the button beside it does:
        # the price is the last thing typed, every time.
        self._unit_price.returnPressed.connect(self.submit)

        add_button = QPushButton("Add item")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self.submit)

        row.addLayout(field("Item", self._picker), 1)
        row.addLayout(field("Quantity", self._quantity))
        row.addLayout(field("Unit price", self._unit_price))
        row.addLayout(field("", add_button))

        self._on_kind_changed()

    # ---------------- state ----------------

    def _on_kind_changed(self, _item_type: ItemType | None = None) -> None:
        """Offer this kind's opening page.

        Whatever was handed over goes in straight away, so the row is
        never briefly empty; a row that searches the shop then asks for
        the kind's first page on top of it.

        The kind is read off the field rather than taken from the signal,
        so this says the same thing however it was reached.
        """
        item_type = self._picker.selected_type()
        self._picker.set_options(
            item_type, self._catalogues.get(item_type, []), keep_selected=False
        )
        if self._search is not None:
            self._search(item_type, "")

    def set_options(self, item_type: ItemType, records: list, term: str | None = None) -> None:
        """Take up matches that came back for what was typed."""
        self._picker.set_options(item_type, records, term=term)

    def _on_item_changed(self, item_type: ItemType, item_id: int | None) -> None:
        if item_id is not None:
            self.itemChanged.emit(item_type, item_id)

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
        self._picker.focus_search()

    # ---------------- adding ----------------

    def submit(self) -> None:
        item_id = self._picker.selected_id()
        if item_id is None:
            self.rejected.emit("Choose an item to add.")
            self._picker.focus_search()
            return

        unit_price = parse_amount(self._unit_price.text())
        if unit_price is None:
            self.rejected.emit("Enter a unit price for this item.")
            self._unit_price.setFocus()
            return

        self.added.emit(
            PickedItem(
                item_type=self._picker.selected_type(),
                item_id=item_id,
                label=self._picker.selected_label(),
                quantity=self._quantity.value(),
                unit_price=unit_price,
            )
        )
