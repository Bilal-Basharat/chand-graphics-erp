"""
Generic read-only table model driven by column specs, so screens don't
each need their own QAbstractTableModel subclass. Backed by QTableView
(not QTableWidget) so it stays fast at hundreds/thousands of rows.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

RowT = TypeVar("RowT")

Alignment = Literal["left", "center", "right"]

_ALIGNMENT_FLAGS: dict[Alignment, Qt.AlignmentFlag] = {
    "left": Qt.AlignmentFlag.AlignLeft,
    "center": Qt.AlignmentFlag.AlignCenter,
    "right": Qt.AlignmentFlag.AlignRight,
}

_TABULAR_FONT: QFont | None = None


def _tabular_font() -> QFont:
    """The application font with tabular (fixed-width) figures.

    Built once and shared: `data()` is called for every visible cell on
    every repaint, so constructing a QFont per call would be wasteful.
    """
    global _TABULAR_FONT
    if _TABULAR_FONT is None:
        font = QApplication.font()
        font.setFeature(QFont.Tag("tnum"), 1)
        _TABULAR_FONT = font
    return _TABULAR_FONT


@dataclass(slots=True)
class Column(Generic[RowT]):
    header: str
    getter: Callable[[RowT], Any]
    align: Alignment = "left"
    color: Callable[[RowT], str | None] | None = None  # optional per-row hex color for this column
    sort_key: Callable[[RowT], Any] | None = None
    """What to order by when a list is ordered here rather than by the
    database — the detail rows under a document, which are the whole of
    that document and are never a page of it.

    Defaults to the getter, which is right for text. Anything the getter
    formats — money, dates, counts — needs the raw value here instead, or
    the column sorts the way the *string* reads: "1,000.00" before
    "500.00".
    """
    sort_field: str | None = None
    """What the query calls this column, for a list the database orders.

    A page can only be sorted by the whole list's order, so the heading
    asks for that order by name and gets a different page back. `None`
    means this column cannot be sorted on: the heading then carries no
    mark and refuses the click, rather than appearing to sort and handing
    back the same rows.
    """
    width: int | None = None
    """
    Fixed pixel width. `None` means the column shares the leftover space
    with the other unset columns.

    The rule of thumb every screen follows: give a width to columns whose
    content has a known short length (codes, counts, money, status), leave
    it unset on the free-text columns (names, descriptions). Without this,
    Qt's default sizing lets one column swallow the window while the rest
    stay cramped.
    """


def _blank(_row: Any) -> str:
    return ""


def detail_columns(
    columns: Sequence[Column],
    under: dict[str, tuple[str, Callable[[Any], Any]]],
) -> list[Column]:
    """Detail columns that line up under named parent columns.

    A grouped table's child rows share the parent's column geometry, so a
    detail row is written here as "under this parent heading, show a
    column called that" rather than as a second list of widths to keep in
    step with the first by hand. Parent columns with no entry render
    empty on the detail rows.
    """
    return [
        Column(
            under.get(column.header, ("", _blank))[0],
            under.get(column.header, ("", _blank))[1],
            align=column.align,
            width=column.width,
        )
        for column in columns
    ]


def safe_value(getter: Callable[[RowT], Any], row: RowT) -> Any:
    """
    Column getters run inside Qt's paint path, where an exception aborts
    the repaint and can take the window down. A single bad record — a
    domain property that raises on inconsistent data, say — should cost one
    cell, not the screen. The failure is logged rather than swallowed.
    """
    try:
        return getter(row)
    except Exception:  # noqa: BLE001 - deliberate: never let paint raise
        logger.exception("Table column getter failed for row %r", row)
        return "—"


def cell_alignment(column: Column[RowT]) -> int:
    """The alignment a column's cells *and* its heading use.

    Qt centres header text by default while cells follow their own
    alignment, so a right-aligned amount sat under a centred heading and
    the two read as unrelated.
    """
    return int(_ALIGNMENT_FLAGS[column.align] | Qt.AlignmentFlag.AlignVCenter)


def column_data(column: Column[RowT], row: RowT, role: int) -> Any:
    """One cell's value for one Qt role.

    Shared by the flat and grouped models so a `Column` renders the same
    whichever table it lands in.
    """
    if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
        value = safe_value(column.getter, row)
        return "" if value is None else str(value)

    if role == Qt.ItemDataRole.TextAlignmentRole:
        return cell_alignment(column)

    if role == Qt.ItemDataRole.FontRole and column.align == "right":
        # Right-aligned columns are the numeric ones. Tabular figures give
        # every digit the same width, so amounts line up column-wise
        # instead of drifting with the glyphs that happen to be in each
        # number.
        return _tabular_font()

    if role == Qt.ItemDataRole.ForegroundRole and column.color is not None:
        hex_color = safe_value(column.color, row)
        return QColor(hex_color) if hex_color else None

    return None


class SimpleTableModel(QAbstractTableModel, Generic[RowT]):
    def __init__(
        self,
        columns: Sequence[Column[RowT]],
        rows: list[RowT] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._columns = list(columns)
        self._rows: list[RowT] = rows or []

    def set_rows(self, rows: list[RowT]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def refresh(self) -> None:
        """Re-render current rows in place (e.g. after a lookup used by a formatter changes)."""
        if self._rows:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._rows) - 1, len(self._columns) - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def row_at(self, row_index: int) -> RowT:
        return self._rows[row_index]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt override)
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802 (Qt override)
        if parent.isValid():
            return 0
        return len(self._columns)

    def headerData(  # noqa: N802 (Qt override)
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if orientation != Qt.Orientation.Horizontal:
            return str(section + 1) if role == Qt.ItemDataRole.DisplayRole else None

        if role == Qt.ItemDataRole.DisplayRole:
            return self._columns[section].header

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return cell_alignment(self._columns[section])

        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802 (Qt override)
        if not index.isValid():
            return None
        return column_data(self._columns[index.column()], self._rows[index.row()], role)
