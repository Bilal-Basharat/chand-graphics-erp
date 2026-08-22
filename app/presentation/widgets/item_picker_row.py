"""
The one way a line gets added to a document: type, item, quantity, unit
price, Add — in a single line above the list it adds to.

A unit box sits beside the quantity, and **only for an item that has more
than one**. A shop that counts everything one way never sees it; one that
buys A4 by the box and sells it by the piece picks which it means, and
the price it types is a price for that unit.

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

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from app.domain.enums.item_type import ItemType
from app.presentation.widgets.form_field import field
from app.presentation.widgets.item_search_field import ItemDelegate, ItemSearchField
from app.presentation.widgets.input_validation import MoneyInput, parse_amount
from app.presentation.widgets.modern_spinbox import ModernDecimalSpinBox

__all__ = ["ItemDelegate", "ItemPickerRow", "PickedItem"]

_UNCAPPED = Decimal("1000000")

_BASE_UNIT = None
"""What the unit box holds for "the item's own unit" — the same None a
document line stores in `uom_id`."""

_DEFAULT_UNIT = "Unit"
"""What the item's own unit is called when the shop never named one."""


@dataclass(frozen=True, slots=True)
class PickedItem:
    """A complete choice, ready to become a document line."""

    item_type: ItemType
    item_id: int
    label: str
    quantity: Decimal
    unit_price: Decimal
    uom_id: int | None = None
    """Which of the item's units the quantity is in, or None for its own.
    The price goes with it: 5,000 a Box is not 5,000 a Piece."""

    unit_label: str | None = None
    """That unit's name, for the line to show."""

    base_quantity: Decimal = Decimal("1")
    """The same quantity in the item's own unit — what the shelf moves by,
    and the only way lines counted differently can be added together."""


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
        self._base_unit_label = _DEFAULT_UNIT
        self._factors: dict[int | None, Decimal] = {_BASE_UNIT: Decimal("1")}
        self._base_limit: Decimal | None = None
        """What the shelf holds, in base units. Kept because the cap on
        the quantity box is in whichever unit is chosen, and that changes
        under it."""

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

        self._quantity = ModernDecimalSpinBox()
        self._quantity.setRange(0, _UNCAPPED)
        self._quantity.setValue(1)

        # Hidden until the chosen item has more than one unit, which for
        # most of a shop's catalogue is never. An empty dropdown offering
        # one choice is a question with no answer to give.
        self._unit = QComboBox()
        self._unit.setMinimumWidth(110)
        self._unit.currentIndexChanged.connect(self._on_unit_changed)
        self._unit_field = field("Unit", self._unit)

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
        row.addLayout(self._unit_field)
        row.addLayout(field("Unit price", self._unit_price))
        row.addLayout(field("", add_button))

        self._show_units(())
        self._on_kind_changed()

    # ---------------- state ----------------

    def set_units(self, units: Sequence) -> None:
        """The units the chosen item may be traded in.

        The item's own unit is always first and always available; what
        arrives here are its alternates. Called when the item changes, so
        a unit left over from the last item can never be submitted
        against this one.
        """
        self._show_units(units)

    def _show_units(self, units: Sequence) -> None:
        self._factors = {_BASE_UNIT: Decimal("1")}
        self._unit.blockSignals(True)
        self._unit.clear()
        self._unit.addItem(self._base_unit_label, _BASE_UNIT)
        for unit in units:
            self._unit.addItem(unit.name, unit.id)
            self._factors[unit.id] = Decimal(unit.factor)
        self._unit.setCurrentIndex(0)
        self._unit.blockSignals(False)

        visible = bool(units)
        self._unit.setVisible(visible)
        for position in range(self._unit_field.count()):
            widget = self._unit_field.itemAt(position).widget()
            if widget is not None:
                widget.setVisible(visible)

    def _on_unit_changed(self, _position: int) -> None:
        """A quantity means something different in a different unit.

        The box is capped in whatever is chosen, so the cap is worked out
        again — ten boxes and 2,880 pieces are the same shelf.
        """
        self._quantity.setValue(1)
        self.set_quantity_limit(self._base_limit)

    def set_base_unit(self, unit: str | None) -> None:
        """What the item's own unit is called, for the first choice."""
        self._base_unit_label = unit or _DEFAULT_UNIT
        if self._unit.count():
            self._unit.setItemText(0, self._base_unit_label)

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

    def set_quantity_limit(self, limit: Decimal | None) -> None:
        """Cap what can be typed into the quantity, for a document that has
        one — a sale cannot be for more than is on the shelf.

        Refusing the number as it is typed beats accepting it and then
        explaining, and it is the same cap the use case would apply.

        The cap is in base units and the box may be counting in another,
        so it is converted the way the line will be. A limit of zero is
        left at zero rather than raised to one: an item with nothing on
        the shelf has nothing that can be typed.
        """
        self._base_limit = limit
        capped = _UNCAPPED if limit is None else max(Decimal("0"), Decimal(limit))
        self._quantity.setRange(0, capped / self._factor())

    def _factor(self) -> Decimal:
        """How many base units the chosen unit is worth. One, unless a
        unit other than the item's own has been picked."""
        return self._factors.get(self._unit.currentData(), Decimal("1"))

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

        if self._quantity.value() <= 0:
            self.rejected.emit("Enter how many of these are on this line.")
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
                uom_id=self._unit.currentData(),
                unit_label=self._unit.currentText(),
                base_quantity=self._quantity.value() * self._factor(),
                unit_price=unit_price,
            )
        )
