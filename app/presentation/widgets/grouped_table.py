"""
A list where each row can open to reveal the records behind it.

An invoice settled in three instalments is one debt, not three. Listing
the instalments as siblings of the invoices buries the thing the user came
to look at — what is still owed — under the history of how it was paid.
So the invoice stays a single row carrying its own totals, and its
payments live underneath it, one disclosure away.

Detail rows reuse the parent's column geometry with their own getters:
they are a different record type, so they need their own accessors, but
sharing the grid keeps amounts under amounts and dates under dates. Any
trailing parent column with no detail counterpart simply renders empty.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont, QPaintEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QTreeView, QWidget

from app.presentation.theme import tokens as t
from app.presentation.widgets.data_table import apply_column_sizing, paint_placeholder
from app.presentation.widgets.sortable_header import SortableHeader
from app.presentation.widgets.table_model import Column, cell_alignment, column_data

_TOP_LEVEL = 0
"""Internal id of a top-level index. Children carry their parent's row + 1,
so 0 is free to mean "no parent" — no per-node objects to keep alive."""

_CAPTION_FONT: QFont | None = None


def _caption_font() -> QFont:
    """The detail caption row's type: the column headings' own, one step
    down, so it reads as a heading for the block rather than as data."""
    global _CAPTION_FONT
    if _CAPTION_FONT is None:
        font = QApplication.font()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        _CAPTION_FONT = font
    return _CAPTION_FONT


def _caption_data(column: Column, role: int):
    if role == Qt.ItemDataRole.DisplayRole:
        return column.header
    if role == Qt.ItemDataRole.TextAlignmentRole:
        return cell_alignment(column)
    if role == Qt.ItemDataRole.FontRole:
        return _caption_font()
    if role == Qt.ItemDataRole.ForegroundRole:
        return QColor(t.MUTED)
    return None


class GroupedTableModel(QAbstractItemModel):
    def __init__(
        self,
        columns: Sequence[Column],
        detail_columns: Sequence[Column],
        children_of: Callable[[object], list],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._columns = list(columns)
        self._detail_columns = list(detail_columns)
        self._children_of = children_of
        self._rows: list = []
        self._children: list[list] = []
        # Detail rows are a different kind of record from the row they sit
        # under, so their columns mean different things — an amount there
        # is a unit price, not a total. Where the caller has named them,
        # the names are shown as a caption row above them. Derived from
        # the columns themselves rather than asked for separately: naming
        # them and not showing the names would have no other meaning.
        self._caption = any(column.header for column in self._detail_columns)

    # ---------------- data ----------------

    def set_rows(self, rows: list) -> None:
        self.beginResetModel()
        self._rows = rows
        # Resolved once here rather than on each expand: the detail records
        # already came back with their parent, so a lazy fetch would buy
        # nothing and add an async path through the model.
        self._children = [list(self._children_of(row)) for row in rows]
        self.endResetModel()

    def refresh(self) -> None:
        """Re-render current rows — e.g. after a name lookup a getter reads
        has arrived.

        A full reset rather than `dataChanged`, because the detail rows are
        derived at set time and have to be rebuilt too. It costs the
        expansion state, which is why screens call this when the list is
        reloading anyway.
        """
        self.set_rows(self._rows)

    def row_at(self, row_index: int):
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    def parent_row_of(self, index: QModelIndex):
        """The top-level record `index` belongs to, whatever its depth."""
        if not index.isValid():
            return None
        row = index.row() if index.internalId() == _TOP_LEVEL else index.internalId() - 1
        return self.row_at(row)

    def detail_at(self, index: QModelIndex):
        """The detail record at `index`, or None if it is a top-level row
        or the caption row above the details."""
        if not index.isValid() or index.internalId() == _TOP_LEVEL:
            return None
        position = index.row() - 1 if self._caption else index.row()
        if position < 0:
            return None
        return self._children[index.internalId() - 1][position]

    # ---------------- structure ----------------

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(row, column, _TOP_LEVEL)
        return self.createIndex(row, column, parent.row() + 1)

    def parent(self, index: QModelIndex = QModelIndex()) -> QModelIndex:  # noqa: N802 (Qt override)
        if not index.isValid() or index.internalId() == _TOP_LEVEL:
            return QModelIndex()
        return self.createIndex(index.internalId() - 1, 0, _TOP_LEVEL)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt override)
        if not parent.isValid():
            return len(self._rows)
        if parent.internalId() != _TOP_LEVEL:
            return 0  # details have no details of their own
        children = len(self._children[parent.row()])
        return children + 1 if children and self._caption else children

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt override)
        return len(self._columns)

    # ---------------- rendering ----------------

    def headerData(  # noqa: N802 (Qt override)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self._columns[section].header
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return cell_alignment(self._columns[section])
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if index.internalId() == _TOP_LEVEL:
            return column_data(self._columns[index.column()], self._rows[index.row()], role)

        if role == Qt.ItemDataRole.BackgroundRole:
            # The same tint as the column headings, so an opened row reads
            # as one banded block belonging to the row above it rather than
            # as more records in the list. Set on every column, including
            # the parent-only ones, or the band would stop short.
            return QColor(t.CANVAS)

        if index.column() >= len(self._detail_columns):
            return None  # a parent-only column, e.g. a trailing actions column

        column = self._detail_columns[index.column()]
        detail = self.detail_at(index)
        if detail is None:
            return _caption_data(column, role)

        if role == Qt.ItemDataRole.ForegroundRole and column.color is None:
            # Detail rows read as supporting text under the row they belong
            # to, so they are muted unless the column asked for a colour of
            # its own.
            return QColor(t.INK_SOFT)
        return column_data(column, detail, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        # The caption is a label, not a record: it cannot be selected, so
        # clicking it can't leave the screen acting on "the caption row".
        if index.isValid() and index.internalId() != _TOP_LEVEL and self.detail_at(index) is None:
            return Qt.ItemFlag.NoItemFlags
        return super().flags(index)


class GroupedTable(QTreeView):
    """The grouped counterpart of `DataTable` — same column specs, same
    empty state, plus a disclosure arrow on rows that have detail."""

    def __init__(
        self,
        columns: Sequence[Column],
        detail_columns: Sequence[Column],
        children_of: Callable[[object], list],
        placeholder: str = "Nothing to show yet.",
        start_expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._placeholder = placeholder
        # A list of records opens closed — the detail is an answer to a
        # question the user has not asked yet. A picker opens open: its
        # groups are shelves, and a shelf you have to click to see into is
        # an obstacle, not a summary.
        self._expanded = start_expanded
        self._model = GroupedTableModel(columns, detail_columns, children_of, self)
        self.setModel(self._model)

        self._sorting = SortableHeader(columns, self)
        self._sorting.install(self)

        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.setUniformRowHeights(True)
        self.setRootIsDecorated(True)
        self.setIndentation(20)
        # Double-click is the screen's own shortcut (open the record), so
        # the arrow is the only thing that expands. Otherwise one gesture
        # would do two unrelated jobs.
        self.setExpandsOnDoubleClick(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self._widths = apply_column_sizing(self, columns)

    @property
    def sorting(self) -> SortableHeader:
        return self._sorting

    # ---------------- data ----------------

    def set_rows(self, rows: list) -> None:
        self._model.set_rows(rows)
        if self._expanded:
            self.expandAll()
        self.viewport().update()

    def refresh(self) -> None:
        self._model.refresh()
        if self._expanded:
            self.expandAll()

    def row_count(self) -> int:
        return self._model.rowCount()

    def row_at(self, row_index: int):
        return self._model.row_at(row_index)

    def detail_at(self, index: QModelIndex):
        """The detail record at `index`, or None if it is a top-level row."""
        return self._model.detail_at(index)

    def selected_row(self):
        """The top-level record under the selection.

        Selecting a detail row means its parent: every action this screen
        offers is an action on the document, and making the user re-aim at
        the header row after clicking a payment would be pedantry.
        """
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.parent_row_of(indexes[0])

    def set_placeholder(self, text: str) -> None:
        if text == self._placeholder:
            return
        self._placeholder = text
        self.viewport().update()

    # ---------------- painting ----------------

    def drawRow(self, painter, option, index: QModelIndex) -> None:  # noqa: N802 (Qt override)
        # A QSS rule on `QTreeView::item` hands item drawing to Qt's
        # stylesheet style, and that path ignores `Qt.BackgroundRole`
        # entirely. The tint on a detail row isn't decoration — it is what
        # marks the row as belonging to the one above it — so it is filled
        # in here rather than lost. Done at the row level, not in a
        # delegate, so the indentation under the disclosure arrow is
        # covered too instead of leaving a white notch.
        background = index.data(Qt.ItemDataRole.BackgroundRole)
        if isinstance(background, QColor):
            painter.fillRect(option.rect, background)
        super().drawRow(painter, option, index)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        super().paintEvent(event)
        if self._model.rowCount() == 0:
            paint_placeholder(self, self._placeholder)
