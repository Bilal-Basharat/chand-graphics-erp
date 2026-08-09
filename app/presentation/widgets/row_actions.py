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

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QAbstractItemView, QStyledItemDelegate, QToolTip

from app.presentation.theme import tokens as t
from app.presentation.widgets.nav_icons import ICON_SIZE, icon_pixmap

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

# A flat grey chip, the same treatment every other disabled button in the
# app gets — see the [variant="primary"]:disabled rule in the stylesheet.
_DISABLED = (t.LINE, t.LINE, t.MUTED)


def _shows(action: "RowAction", label: str) -> bool:
    """Whether this row draws this action at all.

    An icon button always does. A worded one stops when `label_of` returns
    nothing, which is how a row says the action has no meaning on it — a
    delivered job has no next status to move to.
    """
    return bool(label) or action.icon is not None


@dataclass(frozen=True, slots=True)
class RowAction:
    key: str
    label: str
    """The button's text, and the width its slot reserves.

    When `label_of` is set this is the widest text that can appear, so the
    buttons stay in line down the column instead of shifting row by row.
    Empty for an icon button, which reserves a square instead.
    """
    tone: Tone = "default"
    icon: str | None = None
    """A drawing from `nav_icons` to put in the button instead of words.

    For an action that appears on every list in the app: said once as a
    mark, it stays out of the way of the record beside it, where the same
    word repeated down seven screens would not. Anything screen-specific
    keeps its label — an icon nobody can name is a worse button than a
    wide one.
    """
    hint: str = ""
    """Tooltip. Required in practice for an icon button, which otherwise
    asks the user to guess."""
    label_of: Callable[[Any], str] | None = None
    """This row's own text, for an action whose wording depends on the
    record — "Mark completed" against one job, "Mark delivered" against
    the next. Returning an empty string leaves the slot blank, for a row
    the action has nothing to do on at all."""
    enabled_of: Callable[[Any], bool] | None = None
    """Whether this row's button can be clicked. A disabled one is drawn
    greyed rather than removed, so it still reads as an action that exists
    and simply does not apply here."""


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
            (ICON_SIZE if action.icon else metrics.horizontalAdvance(action.label))
            + 2 * _PADDING_X
            for action in self._actions
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

    @staticmethod
    def _acts_on(index: QModelIndex) -> bool:
        """Whether this row is one the actions can act on.

        Only top-level rows are. In a grouped list the child rows are the
        detail of the row above them — the lines of an invoice, the items
        of a job — and an "Edit" on one of those has nothing to edit. A
        flat table has no children, so this is always true there.
        """
        return index.isValid() and not index.parent().isValid()

    def _resolved(self, index: QModelIndex) -> list[tuple[RowAction, str, bool]]:
        """Each action as this row takes it: its text, and whether it is live.

        Both tables expose `row_at`, and it returns None for an index that
        has outlived the rows it was painted against — a click landing
        after a reload. The static wording stands in for that, which is
        what an action with no per-row callbacks shows anyway.
        """
        row = self._view.row_at(index.row()) if self._view is not None else None
        return [
            (
                action,
                action.label_of(row) if action.label_of and row is not None else action.label,
                action.enabled_of(row) if action.enabled_of and row is not None else True,
            )
            for action in self._actions
        ]

    def _hit(self, pos: QPoint) -> tuple[QModelIndex, int] | None:
        if self._view is None:
            return None
        index = self._view.indexAt(pos)
        if index.column() != self._column or not self._acts_on(index):
            return None
        resolved = self._resolved(index)
        for action_index, rect in enumerate(self._button_rects(self._view.visualRect(index))):
            action, label, enabled = resolved[action_index]
            if _shows(action, label) and enabled and rect.contains(pos):
                return index, action_index
        return None

    # ---------------- painting ----------------

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        # The base draws the row background, selection tint and separator
        # for us; the column's text is empty, so nothing else lands.
        super().paint(painter, option, index)
        if not self._acts_on(index):
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self._font)
        for position, ((action, label, enabled), rect) in enumerate(
            zip(self._resolved(index), self._button_rects(option.rect))
        ):
            if not _shows(action, label):
                continue  # nothing to do on this row; the slot keeps its width
            hovered = enabled and self._hover == (index.row(), position)
            border, background, text = (
                _STYLES[(action.tone, hovered)] if enabled else _DISABLED
            )
            painter.setPen(QColor(border))
            painter.setBrush(QColor(background))
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), _RADIUS, _RADIUS)
            if action.icon:
                # Tinted to whatever the button's text would have been, so
                # an icon button hovers and greys like a worded one. Drawn
                # at a point rather than into a rect: the pixmap already
                # carries the display's pixel ratio, and scaling it into a
                # box would resample what was drawn to fit exactly.
                box = QRect(0, 0, ICON_SIZE, ICON_SIZE)
                box.moveCenter(rect.center())
                painter.drawPixmap(box.topLeft(), icon_pixmap(action.icon, text))
            else:
                painter.setPen(QColor(text))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def helpEvent(self, event, view, option, index) -> bool:  # noqa: N802 (Qt override)
        """The tooltip for the button under the pointer, not for the cell.

        An icon button has to say what it is somewhere, and Qt's own
        tooltip machinery only knows about cells — so the hit test that
        already decides what a click lands on decides this too.
        """
        if event.type() == QEvent.Type.ToolTip and self._view is not None:
            hit = self._hit(self._view.viewport().mapFromGlobal(event.globalPos()))
            if hit is not None:
                hint = self._actions[hit[1]].hint
                if hint:
                    QToolTip.showText(event.globalPos(), hint, self._view)
                    return True
            QToolTip.hideText()
        return super().helpEvent(event, view, option, index)

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
