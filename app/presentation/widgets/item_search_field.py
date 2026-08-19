"""
"Which item?", as one control: the kind, and a box you type a name into.

Every screen that acts on stock has to ask this, and each of them was
asking it the same way — an `ItemTypeCombo` beside a `SearchableComboBox`,
a search callback wired to one and read off the other, and the answer
coerced back to an `ItemType` at the end. That pairing is written once
here, and the screens keep only what is actually theirs.

Searched rather than scrolled: the list is a whole shop's catalogue, and
the item being picked is one name in it. Matches are asked for as the box
is typed into — see `searchable_combo.py` — because past whatever a
catalogue was capped at, the item simply was not in the box.

The field reports; it decides nothing. `itemChanged` is whatever is
selected now, `itemChosen` is the user actively picking one — the
difference matters to a caller that answers a choice with a message,
which nobody wants to meet on opening a form.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from app.domain.enums.item_type import ItemType
from app.presentation.item_types import item_name
from app.presentation.theme import tokens as t
from app.presentation.widgets.item_type_combo import ItemTypeCombo
from app.presentation.widgets.searchable_combo import SearchableComboBox

NONE_AVAILABLE = "— none available —"

STOCK_ROLE = Qt.ItemDataRole.UserRole + 1
"""Where a row keeps the count it had when it was offered, for the
delegate that paints it at the right-hand edge."""


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
        stock = index.data(STOCK_ROLE)
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


class ItemSearchField(QWidget):
    searchRequested = Signal(object, str)
    """ItemType, term — matches are wanted for what has been typed."""

    itemChanged = Signal(object, object)
    """ItemType, item id or None — whatever is selected now."""

    itemChosen = Signal(object, int)
    """ItemType, item id — and the user picked it."""

    kindChanged = Signal(object)
    """ItemType — another catalogue entirely, so whatever was offered no
    longer applies. Kept apart from `searchRequested` because a host may
    hand its catalogue over whole and still need to know the kind moved."""

    def __init__(
        self,
        *,
        placeholder: str = "Type any part of an item's name to find it",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stock: dict[tuple[ItemType, int], int] = {}
        """What each item had in stock when it was last offered. Kept
        across searches so the figure beside a row survives a refill."""

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self.kind = ItemTypeCombo()
        self.kind.currentIndexChanged.connect(self._on_kind_changed)

        self.item = SearchableComboBox()
        self.item.setItemDelegate(ItemDelegate(self.item))
        self.item.setToolTip(placeholder)
        self.item.setMinimumWidth(220)
        self.item.currentIndexChanged.connect(self._on_item_changed)
        self.item.activated.connect(self._on_item_chosen)
        self.item.searchRequested.connect(
            lambda term: self.searchRequested.emit(self.selected_type(), term)
        )

        row.addWidget(self.kind)
        row.addWidget(self.item, 1)

    # ---------------- reading ----------------

    def selected_type(self) -> ItemType:
        return self.kind.selected_type()

    def selected_id(self) -> int | None:
        return self.item.currentData()

    def selected_label(self) -> str:
        """The selected row's own name, not the text in the box — which
        can hold something half-typed towards it."""
        return self.item.itemText(self.item.currentIndex())

    # ---------------- filling ----------------

    def set_options(
        self,
        item_type: ItemType,
        records: list,
        term: str | None = None,
        *,
        keep_selected: bool = True,
    ) -> None:
        """Take up matches that came back for what was typed.

        Ignored if the field has moved on to another kind since asking —
        offering paper under "Ink" would be a list nobody asked for.
        """
        if ItemType(item_type) != self.selected_type():
            return

        self._stock.update(
            {
                (ItemType(item_type), record.id): getattr(record, "current_stock", 0)
                for record in records
            }
        )
        rows = [(item_name(item_type, record), record.id) for record in records]
        if not rows and term is None:
            self.item.set_placeholder_item(NONE_AVAILABLE, None)
        self.item.set_options(rows, term=term, keep_selected=keep_selected)
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
        with self.item.keeping_typed_text():
            for index in range(self.item.count()):
                item_id = self.item.itemData(index)
                if item_id is None:
                    continue
                self.item.setItemData(
                    index, self._stock.get((ItemType(item_type), item_id)), STOCK_ROLE
                )

    def focus_search(self) -> None:
        self.item.focus_search()

    # ---------------- signals ----------------

    def _on_kind_changed(self, _index: int) -> None:
        # Nothing carried over: what was picked in the last catalogue is
        # not a choice in this one, and ids are only unique within a kind
        # — kept, the same number would name a different record here.
        self.item.set_options([], keep_selected=False)
        self.kindChanged.emit(self.selected_type())
        self._on_item_changed()

    def _on_item_changed(self, _index: int = 0) -> None:
        self.itemChanged.emit(self.selected_type(), self.selected_id())

    def _on_item_chosen(self, _index: int) -> None:
        item_id = self.selected_id()
        if item_id is not None:
            self.itemChosen.emit(self.selected_type(), item_id)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # The field fills itself while it is being constructed, which is
        # before its host has had a chance to connect — so the first
        # selection would otherwise be the one nobody was told about, and
        # a sale would open with its quantity uncapped.
        self._on_item_changed()
