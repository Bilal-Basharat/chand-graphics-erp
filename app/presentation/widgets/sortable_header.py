"""
Column headings that sort the list when clicked.

Sorting used to be a dropdown beside the search box, which meant reading
a list of sentences ("Biggest total", "Oldest first") to do something the
column you are already looking at could do directly. Clicking the heading
is where people try first.

Every sortable heading carries the mark — two small triangles, dimmed —
so it is visible that the column *can* be sorted before anything is
clicked. The column being sorted by lights up the triangle for its
direction. Qt's own indicator only appears on the active column, which
leaves every other heading looking inert.

Drawn with QPainter for the same reason the navigation icons are (see
nav_icons.py): one stroke, one box, one colour, no font dependency.
"""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHeaderView, QWidget

from app.presentation.theme import tokens as t
from app.presentation.widgets.table_model import Column

_PADDING = 12
"""The side padding the QSS gives `QHeaderView::section`. The mark is
placed against the heading text, so it has to start from the same edge
the text does."""
_TEXT_GAP = 7
"""Space between the end of the heading and the middle of the mark."""
_HALF_WIDTH = 3.6
_HEIGHT = 4.0
_GAP = 1.8


class SortableHeader(QHeaderView):
    changed = Signal()

    def __init__(self, columns: Sequence[Column], parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._columns = list(columns)
        self._column: int | None = None
        self._descending = False

        self.sectionClicked.connect(self._on_clicked)

    def install(self, view) -> None:
        """Attach to a view, and put back what attaching takes away.

        `QTreeView.setHeader` re-derives clickability from the view's own
        `sortingEnabled` flag, which is off — Qt's built-in sorting sorts
        the *model*, which is not what happens here. Set the moment after,
        or a header installed the obvious way arrives unclickable.
        """
        if hasattr(view, "setHeader"):
            view.setHeader(self)
        else:
            view.setHorizontalHeader(self)
        self.setSectionsClickable(True)
        self.setHighlightSections(False)

    # ---------------- state ----------------

    def sort_by(self, header: str, descending: bool = False) -> None:
        """Open the list on a particular order, named by its heading.

        Marks the heading without asking for anything: the caller is
        saying what the list is *already* ordered by. `CollectionView.
        set_initial_sort` is what tells the view model at the same time —
        set only this and the heading claims an order the query never
        applied.
        """
        for index, column in enumerate(self._columns):
            if column.header == header:
                self._column = index
                self._descending = descending
                self.viewport().update()
                return

    @property
    def sort_field(self) -> str | None:
        """What the query calls the column being sorted by."""
        if self._column is None:
            return None
        return self._columns[self._column].sort_field

    @property
    def descending(self) -> bool:
        return self._descending

    def _sortable(self, index: int) -> bool:
        # An unlabelled column is either the row-actions column or a detail
        # column: nothing a user would think to sort by. A labelled one
        # without a `sort_field` is a column the query cannot order by, and
        # a heading that answers a click by returning the same rows is
        # worse than one that does not react at all.
        if not 0 <= index < len(self._columns):
            return False
        column = self._columns[index]
        return bool(column.header) and column.sort_field is not None

    def _on_clicked(self, index: int) -> None:
        if not self._sortable(index):
            return
        if self._column == index:
            self._descending = not self._descending
        else:
            self._column = index
            self._descending = False
        self.viewport().update()
        self.changed.emit()

    # ---------------- painting ----------------

    def paintSection(self, painter: QPainter, rect, index: int) -> None:  # noqa: N802 (Qt override)
        super().paintSection(painter, rect, index)
        if not self._sortable(index):
            return

        centre_x = self._mark_x(self._columns[index], rect)
        centre_y = rect.center().y() + 1

        # Grey enough to sit behind the heading, dark enough to be seen at
        # all: at the panel-line grey these read as smudges on a white
        # header and nobody knows the column can be clicked.
        active = index == self._column
        up = t.PRIMARY if active and not self._descending else t.MUTED
        down = t.PRIMARY if active and self._descending else t.MUTED

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        _triangle(painter, centre_x, centre_y - _GAP, -_HEIGHT, up)
        _triangle(painter, centre_x, centre_y + _GAP, _HEIGHT, down)
        painter.restore()


    def _mark_x(self, column: Column, rect) -> float:
        """Where the mark sits: just past the heading, on whichever side
        the heading's own alignment leaves free.

        Pinning it to the section's edge instead put it hard against the
        text on a right-aligned column and a column's width away from it on
        a left-aligned one — the same mark reading as two different
        relationships. Following the text keeps one gap everywhere.
        """
        text = self.fontMetrics().horizontalAdvance(column.header)
        if column.align == "right":
            centre = rect.right() - _PADDING - text - _TEXT_GAP
        elif column.align == "center":
            centre = rect.center().x() + text / 2 + _TEXT_GAP
        else:
            centre = rect.left() + _PADDING + text + _TEXT_GAP
        # A heading wider than its column is elided; keep the mark inside
        # the section rather than letting it drift into the neighbour.
        return min(
            max(centre, rect.left() + _HALF_WIDTH + 2),
            rect.right() - _HALF_WIDTH - 2,
        )


def _triangle(painter: QPainter, x: float, y: float, height: float, color: str) -> None:
    painter.setBrush(QColor(color))
    painter.drawPolygon(
        [
            QPointF(x - _HALF_WIDTH, y),
            QPointF(x + _HALF_WIDTH, y),
            QPointF(x, y + height),
        ]
    )
