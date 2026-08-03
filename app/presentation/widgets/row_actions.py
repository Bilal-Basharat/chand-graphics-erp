"""
Per-row action buttons painted inside a table column.

A shared toolbar of "Edit line" / "Remove line" buttons above a table asks
the user to do two things to act on one row: select it, then find the
button. Which row it will act on is never visible. Putting the buttons in
the row removes both problems — the target is wherever the pointer already
is.

Painted by a delegate rather than a widget per row: a `QPushButton` in
every row costs a widget tree per record and stops scaling long before a
table does. The delegate draws the same pixels for any number of rows.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractItemView, QStyledItemDelegate

from app.presentation.theme import tokens as t

Tone = Literal["default", "danger"]

_PADDING_X = 11
_GAP = 6
_MARGIN = 12
_HEIGHT = 24
_RADIUS = 5

# (border, background, text) per tone, resting and hovered.
_STYLES: dict[tuple[Tone, bool], tuple[str, str, str]] = {
    ("default", False): (t.LINE, t.SURFACE, t.INK_SOFT),
    ("default", True): (t.PRIMARY, t.PRIMARY_TINT, t.PRIMARY),
    ("danger", False): (t.LINE, t.SURFACE, t.DANGER),
    ("danger", True): (t.DANGER, t.DANGER_TINT, t.DANGER),
}


@dataclass(frozen=True, slots=True)
class RowAction:
    key: str
    label: str
    tone: Tone = "default"


class RowActionsDelegate(QStyledItemDelegate):
    """Draws `actions` as small buttons in one column and reports clicks.

    `triggered` carries the action key and the model row, so the host
    screen acts on the row that was clicked — not on whatever happens to
    be selected.
    """

    triggered = Signal(str, int)  # action key, row index

    def __init__(self, actions: Sequence[RowAction], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._actions = list(actions)
        self._view: QAbstractItemView | None = None
        self._column = 0
        self._hover: tuple[int, int] | None = None  # (row, action index)

        self._font = QFont(t.FONT_FAMILY)
        self._font.setPixelSize(12)
        self._font.setWeight(QFont.Weight.Medium)
        metrics = QFontMetrics(self._font)
        self._widths = [
            metrics.horizontalAdvance(action.label) + 2 * _PADDING_X for action in self._actions
        ]

    # ---------------- wiring ----------------

    def column_width(self) -> int:
        """Exactly the space the buttons need — no guessed constant."""
        return sum(self._widths) + _GAP * (len(self._widths) - 1) + 2 * _MARGIN

    def attach(self, view: QAbstractItemView, column: int) -> None:
        """Own the column: delegate, width, and all of its mouse handling.

        The filter goes on the viewport rather than using `editorEvent`,
        because hover has to follow the pointer between buttons and Qt only
        forwards press/release to a delegate.
        """
        self._view = view
        self._column = column
        view.setItemDelegateForColumn(column, self)
        view.setColumnWidth(column, self.column_width())
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)
        # During teardown the view's C++ object can go before this filter is
        # unhooked, and touching it then raises. Drop the reference the
        # moment Qt says the view is gone.
        view.destroyed.connect(self._forget_view)

    def _forget_view(self, *_args: object) -> None:
        self._view = None

    # ---------------- geometry ----------------

    def _button_rects(self, cell: QRect) -> list[QRect]:
        total = sum(self._widths) + _GAP * (len(self._widths) - 1)
        x = cell.right() - _MARGIN - total
        y = cell.center().y() - _HEIGHT // 2
        rects = []
        for width in self._widths:
            rects.append(QRect(x, y, width, _HEIGHT))
            x += width + _GAP
        return rects

    def _hit(self, pos: QPoint) -> tuple[QModelIndex, int] | None:
        if self._view is None:
            return None
        index = self._view.indexAt(pos)
        if not index.isValid() or index.column() != self._column:
            return None
        for action_index, rect in enumerate(self._button_rects(self._view.visualRect(index))):
            if rect.contains(pos):
                return index, action_index
        return None

    # ---------------- painting ----------------

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        # The base draws the row background, selection tint and separator
        # for us; the column's text is empty, so nothing else lands.
        super().paint(painter, option, index)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self._font)
        for position, (action, rect) in enumerate(
            zip(self._actions, self._button_rects(option.rect))
        ):
            hovered = self._hover == (index.row(), position)
            border, background, text = _STYLES[(action.tone, hovered)]
            painter.setPen(QColor(border))
            painter.setBrush(QColor(background))
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), _RADIUS, _RADIUS)
            painter.setPen(QColor(text))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, action.label)
        painter.restore()

    # ---------------- mouse ----------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt override)
        if self._view is None or watched is not self._view.viewport():
            return super().eventFilter(watched, event)

        kind = event.type()
        if kind == QEvent.Type.MouseMove:
            self._set_hover(self._hit(event.position().toPoint()))
        elif kind == QEvent.Type.Leave:
            self._set_hover(None)
        elif kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            # Swallowed so a click on a button neither moves the selection
            # nor reaches the table's double-click handler.
            if event.button() == Qt.MouseButton.LeftButton and self._hit(
                event.position().toPoint()
            ):
                return True
        elif kind == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit(event.position().toPoint())
            if hit is not None:
                index, action_index = hit
                self.triggered.emit(self._actions[action_index].key, index.row())
                return True

        return super().eventFilter(watched, event)

    def _set_hover(self, hit: tuple[QModelIndex, int] | None) -> None:
        hover = (hit[0].row(), hit[1]) if hit is not None else None
        if hover == self._hover:
            return
        self._hover = hover
        viewport = self._view.viewport()
        viewport.setCursor(
            Qt.CursorShape.PointingHandCursor if hover else Qt.CursorShape.ArrowCursor
        )
        viewport.update()
