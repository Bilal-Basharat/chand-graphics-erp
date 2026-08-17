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

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from app.domain.enums.item_type import ItemType
from app.presentation.item_types import item_name
from app.presentation.theme import tokens as t
from app.presentation.widgets.form_field import field
from app.presentation.widgets.item_type_combo import ItemTypeCombo
from app.presentation.widgets.input_validation import MoneyInput, parse_amount
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.searchable_combo import SearchableComboBox

_NONE_AVAILABLE = "— none available —"
_UNCAPPED = 1_000_000
_STOCK_ROLE = Qt.ItemDataRole.UserRole + 1


class ItemDelegate(QStyledItemDelegate):
    """A catalogue row: what the item is called, and what is left of it.

    The figure is painted at the right rather than folded into the name so
    it sits in the same place all the way down the list, and the name is
    elided to the room it leaves rather than running underneath it.

    The row itself goes through the style rather than being drawn by hand,
    so it keeps the hover and the selection every other list in the app
    has — which is what tells you where you are while searching.
    """

    _PADDING = 8
    """What a row is inset by, as the stylesheet sets it — so the figure
    ends where a name on the row above it begins."""

    _GAP = 12
    """The least that may be left between a name and a figure, below which
    the two read as one string."""

    def paint(self, painter, option, index):
        stock = index.data(_STOCK_ROLE)
        if stock is None:
            # The "none available" placeholder has no stock to report.
            super().paint(painter, option, index)
            return

        figure = f"Stock: {stock}"
        room = painter.fontMetrics().horizontalAdvance(figure) + self._GAP + self._PADDING

        row = QStyleOptionViewItem(option)
        self.initStyleOption(row, index)
        widget = row.widget
        style = widget.style() if widget is not None else QApplication.style()

        # Drawn twice, because the row's background has to run its whole
        # width while the name must stop short of the figure. First pass
        # is the background and whether it is the row under the cursor;
        # second is the name, into what the figure leaves. Where to break
        # the name is the style's to decide rather than this delegate's,
        # since the style is what knows the font it will be drawn in.
        name, row.text = row.text, ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, row, painter, widget)

        row.text = name
        row.rect = option.rect.adjusted(0, 0, -room, 0)
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, row, painter, widget)

        painter.save()
        painter.setPen(QColor(t.INK_SOFT))
        painter.drawText(
            option.rect.adjusted(0, 0, -self._PADDING, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            figure,
        )
        painter.restore()


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
        self._stock: dict[tuple[ItemType, int], int] = {}
        """What each item had in stock when it was last offered. Kept
        across searches so the figure beside a row survives a refill."""

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self._kind = ItemTypeCombo()
        self._kind.currentIndexChanged.connect(self._on_kind_changed)

        # Typed into rather than scrolled: a catalogue of a thousand items
        # is a search, not a list.
        self._item = SearchableComboBox()
        self._item.setItemDelegate(ItemDelegate(self._item))
        self._item.setToolTip("Type any part of an item's name to find it")

        self._item.setMinimumWidth(220)
        self._item.currentIndexChanged.connect(self._on_item_changed)
        self._item.activated.connect(self._on_item_chosen)
        if search is not None:
            self._item.searchRequested.connect(
                lambda term: search(self._kind.selected_type(), term)
            )

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

        row.addLayout(field("Type", self._kind))
        row.addLayout(field("Item", self._item), 1)
        row.addLayout(field("Quantity", self._quantity))
        row.addLayout(field("Unit price", self._unit_price))
        row.addLayout(field("", add_button))

        self._on_kind_changed(0)

    # ---------------- state ----------------

    def _on_kind_changed(self, _index: int) -> None:
        item_type = self._kind.selected_type()
        # Nothing carried over: what was picked in the last catalogue is
        # not a choice in this one, and ids are only unique within a kind
        # — kept, the same number would name a different record here.
        self._fill(item_type, self._catalogues.get(item_type, []), keep_selected=False)
        if self._search is not None:
            # Another kind is another catalogue: ask for its opening page.
            self._search(item_type, "")

    def set_options(self, item_type: ItemType, records: list, term: str | None = None) -> None:
        """Take up matches that came back for what was typed.

        Ignored if the row has moved on to another kind since asking —
        offering paper under "Ink" would be a list nobody asked for.
        """
        if ItemType(item_type) != self._kind.selected_type():
            return
        self._fill(item_type, records, term=term)

    def _fill(
        self,
        item_type: ItemType,
        records: list,
        term: str | None = None,
        *,
        keep_selected: bool = True,
    ) -> None:
        self._stock.update(
            {
                (ItemType(item_type), record.id): getattr(record, "current_stock", 0)
                for record in records
            }
        )
        rows = [(item_name(item_type, record), record.id) for record in records]
        if not rows and term is None:
            self._item.set_placeholder_item(_NONE_AVAILABLE, None)
        self._item.set_options(rows, term=term, keep_selected=keep_selected)
        self._stamp_stock(item_type)

    def _stamp_stock(self, item_type: ItemType) -> None:
        """Put each row's stock figure back on it after a refill.

        Done from the running record rather than from the batch, because a
        refill can carry a row the batch did not — the item already chosen
        is kept whatever was searched for.

        Under `keeping_typed_text` because these rows arrived in answer to
        a word that is still being typed: writing to the selected row makes
        the box show that row's name, and the word would be gone.
        """
        with self._item.keeping_typed_text():
            for index in range(self._item.count()):
                item_id = self._item.itemData(index)
                if item_id is None:
                    continue
                self._item.setItemData(
                    index, self._stock.get((ItemType(item_type), item_id)), _STOCK_ROLE
                )

    def _on_item_changed(self, _index: int = 0) -> None:
        item_id = self._item.currentData()
        if item_id is not None:
            self.itemChanged.emit(self._kind.selected_type(), item_id)

    def _on_item_chosen(self, _index: int) -> None:
        """The user picked this one, as opposed to it merely being what the
        row happens to be showing — the difference matters to a caller that
        answers a choice with a message, which nobody wants to be met by on
        opening the form."""
        item_id = self._item.currentData()
        if item_id is not None:
            self.itemChosen.emit(self._kind.selected_type(), item_id)

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
        self._item.focus_search()

    # ---------------- adding ----------------

    def submit(self) -> None:
        item_id = self._item.currentData()
        if item_id is None:
            self.rejected.emit("Choose an item to add.")
            self._item.focus_search()
            return

        unit_price = parse_amount(self._unit_price.text())
        if unit_price is None:
            self.rejected.emit("Enter a unit price for this item.")
            self._unit_price.setFocus()
            return

        self.added.emit(
            PickedItem(
                item_type=self._kind.selected_type(),
                item_id=item_id,
                # The selected row's own name, not the text in the box:
                # the box can hold something half-typed towards it.
                label=self._item.itemText(self._item.currentIndex()),
                quantity=self._quantity.value(),
                unit_price=unit_price,
            )
        )
