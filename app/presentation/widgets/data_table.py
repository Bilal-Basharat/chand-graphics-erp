"""
The one table widget every list screen uses.

Wraps QTableView + SimpleTableModel so screens declare *what* their
columns are (via `Column` specs) and never restate *how* a table should
look or size itself. Two things it owns that were previously re-written
per screen, inconsistently:

- **Column sizing.** Driven entirely by `Column.width`: set means fixed
  pixels, unset means "share the leftover space". Multiple unset columns
  split it evenly rather than one swallowing the window.
- **Empty state.** An empty table with no message reads as a broken
  screen. The placeholder is painted onto the viewport rather than
  swapped in as a separate widget, so the header row stays visible and
  the layout doesn't shift when rows arrive.
"""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

from app.presentation.theme import tokens as t
from app.presentation.widgets.sortable_header import SortableHeader
from app.presentation.widgets.table_model import Column, SimpleTableModel

ROW_HEIGHT = 38


MIN_COLUMN_WIDTH = 64
FLEX_MIN_WIDTH = 150
"""Floor for a column with no declared width — enough for a name."""


def apply_column_sizing(view: QAbstractItemView, columns: Sequence[Column]) -> FlexibleWidths:
    """Fixed pixels where `Column.width` is set, shared space where it isn't
    — and every divider draggable either way.

    Every section is Interactive, never Stretch: a stretched section is
    the one thing Qt will not let the user resize, and a name column that
    is both too narrow and immovable is the worst of both. The leftover
    space is handed out by `FlexibleWidths` instead, which stands down the
    moment a divider is dragged.

    Shared by the flat and grouped tables so a column spec means the same
    thing in both.
    """
    header = view.header() if hasattr(view, "header") else view.horizontalHeader()
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(MIN_COLUMN_WIDTH)
    for index, column in enumerate(columns):
        header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
        view.setColumnWidth(index, column.width or FLEX_MIN_WIDTH)
    return FlexibleWidths(view, columns)


class FlexibleWidths(QObject):
    """Keeps the columns adding up to exactly the width on screen.

    Two things follow from that one rule, and they are the two things a
    table gets wrong otherwise: no strip of dead panel to the right of the
    last column, and no reaching past the edge of the window.

    Dragging a divider therefore behaves like a splitter — the columns to
    its right give up or take back what it gained — rather than pushing
    the whole table sideways. Widening the window is the same move with
    nothing dragged: the difference goes to the columns that declared no
    width of their own, which are the ones holding names.

    Columns stop at `MIN_COLUMN_WIDTH`. Drag far enough that they all hit
    it and the table does overflow — at which point a scrollbar is the
    honest answer, because the content genuinely no longer fits.
    """

    def __init__(self, view: QAbstractItemView, columns: Sequence[Column]) -> None:
        super().__init__(view)
        self._view = view
        self._count = len(columns)
        self._flexible = [
            index for index, column in enumerate(columns) if column.width is None
        ] or list(range(self._count))
        self._applying = False

        header = view.header() if hasattr(view, "header") else view.horizontalHeader()
        header.sectionResized.connect(self._on_section_resized)
        view.viewport().installEventFilter(self)
        # During teardown the view's C++ object can go before this filter is
        # unhooked, and touching it then raises. Drop the reference the
        # moment Qt says the view is gone — same as RowActionsDelegate.
        view.destroyed.connect(self._forget_view)

    def _forget_view(self, *_args: object) -> None:
        self._view = None

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt override)
        if self._view is None:
            return False
        if watched is self._view.viewport() and event.type() == QEvent.Type.Resize:
            self.rebalance()
        return super().eventFilter(watched, event)

    def rebalance(self) -> None:
        """Take up the slack, or give it back, using the flexible columns."""
        if self._view is None:
            return
        total = sum(self._view.columnWidth(index) for index in range(self._count))
        self._spread(self._view.viewport().width() - total, self._flexible)

    def _on_section_resized(self, index: int, old: int, new: int) -> None:
        if self._applying or self._view is None:
            return
        # Whatever this column took, the ones after it give up — and the
        # ones before it if it was the last. Either way the total is
        # unchanged, which is the whole point.
        followers = list(range(index + 1, self._count)) or list(range(index - 1, -1, -1))
        self._spread(old - new, followers)

    def _spread(self, amount: int, over: Sequence[int]) -> None:
        """Share `amount` extra pixels (or, negative, a shortfall) across
        `over`, in order, stopping each column at its minimum."""
        if not amount or not over:
            return
        self._applying = True
        remaining = amount
        for index in over:
            if remaining == 0:
                break
            current = self._view.columnWidth(index)
            width = max(MIN_COLUMN_WIDTH, current + remaining)
            self._view.setColumnWidth(index, width)
            remaining -= width - current
        self._applying = False


def paint_placeholder(view: QAbstractItemView, text: str) -> None:
    """Centre the empty-state message on the viewport.

    Painted onto the viewport rather than swapped in as a separate widget,
    so the header row stays visible and the layout doesn't shift when rows
    arrive.
    """
    painter = QPainter(view.viewport())
    painter.setPen(QColor(t.MUTED))
    painter.drawText(view.viewport().rect(), Qt.AlignmentFlag.AlignCenter, text)


class DataTable(QTableView):
    def __init__(
        self,
        columns: Sequence[Column],
        placeholder: str = "Nothing to show yet.",
        parent: QWidget | None = None,
        *,
        sortable: bool = True,
    ) -> None:
        """`sortable=False` for a table whose order is part of the record.

        A list is sorted to find something in it. The lines of an invoice
        are not a list — they are the invoice, in the order it was
        written — and re-ordering them on screen would leave the printed
        copy disagreeing with what was read.
        """
        super().__init__(parent)
        self._placeholder = placeholder
        self._model: SimpleTableModel = SimpleTableModel(columns)
        self.setModel(self._model)

        self._sorting = SortableHeader(columns, self)
        if sortable:
            self._sorting.install(self)
        else:
            # Kept so `sorting` is always answerable — it sorts nothing
            # while no column is chosen — but hidden: an un-installed
            # header is still a child widget, and Qt would show it over
            # the first rows at its default geometry.
            self._sorting.hide()

        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.horizontalHeader().setHighlightSections(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self._widths = apply_column_sizing(self, columns)

    @property
    def sorting(self) -> SortableHeader:
        return self._sorting

    # ---------------- data ----------------

    def set_rows(self, rows: list) -> None:
        self._model.set_rows(rows)
        self.viewport().update()  # repaint so a stale placeholder can't linger

    def refresh(self) -> None:
        """Re-render current rows — for when a lookup a formatter reads has changed."""
        self._model.refresh()

    def row_count(self) -> int:
        return self._model.rowCount()

    def selected_row(self):
        """The row object under the selection, or None if nothing is selected."""
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.row_at(indexes[0].row())

    def row_at(self, row_index: int):
        """The row object at `row_index`, or None if it is out of range.

        Out of range is reachable in practice: a click lands after the rows
        it was painted against have been replaced by a reload.
        """
        if 0 <= row_index < self._model.rowCount():
            return self._model.row_at(row_index)
        return None

    def fit_to_rows(self, minimum: int = 3, maximum: int = 12) -> None:
        """Size the table to the rows it holds, within bounds.

        For a table sitting on a page that scrolls as a whole. A fixed
        height there means either a scrollbar inside a scrollbar — where
        the outer one hides rows the inner one is trying to show — or dead
        white space under a short list.
        """
        rows = min(max(self._model.rowCount(), minimum), maximum)
        header = self.horizontalHeader().sizeHint().height()
        body = rows * self.verticalHeader().defaultSectionSize()
        self.setFixedHeight(header + body + 2 * self.frameWidth())

    def set_placeholder(self, text: str) -> None:
        """Swap the empty-state message — e.g. 'no results' vs 'nothing yet'."""
        if text == self._placeholder:
            return
        self._placeholder = text
        self.viewport().update()

    # ---------------- empty state ----------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        super().paintEvent(event)
        if self._model.rowCount() == 0:
            paint_placeholder(self, self._placeholder)
