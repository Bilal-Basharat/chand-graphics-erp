"""
Navigation icons drawn with QPainter instead of Unicode glyphs.

Glyph "icons" (▦ ◆ ⚙ …) proved unworkable for a consistent rail: they are
sourced from whichever installed font happens to cover each code point, so
they arrive at different design sizes and stroke weights, and some — the
gear especially — carry emoji presentation and render in full colour on
Windows regardless of variation selectors.

Painting them here fixes all of that at once: one stroke width, one
bounding box, one colour, no font dependency, and they tint to match the
row they sit in.
"""
from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

ICON_SIZE = 14
_STROKE = 1.4
# Drawings are authored inside the icon box with a little breathing room.
_BOX = QRectF(2.0, 2.0, 12.0, 12.0)


def _grid(painter: QPainter) -> None:
    half = _BOX.width() / 2 - 1
    for row in range(2):
        for column in range(2):
            painter.drawRect(
                QRectF(
                    _BOX.left() + column * (half + 2),
                    _BOX.top() + row * (half + 2),
                    half,
                    half,
                )
            )


def _arrow(painter: QPainter, start: QPointF, end: QPointF) -> None:
    painter.drawLine(start, end)
    # Head drawn as two short strokes back along the shaft.
    dx = 1 if end.x() > start.x() else -1
    dy = 1 if end.y() > start.y() else -1
    painter.drawLine(end, QPointF(end.x() - dx * 4.5, end.y()))
    painter.drawLine(end, QPointF(end.x(), end.y() - dy * 4.5))


def _arrow_up_right(painter: QPainter) -> None:
    _arrow(painter, _BOX.bottomLeft(), _BOX.topRight())


def _arrow_down_left(painter: QPainter) -> None:
    _arrow(painter, _BOX.topRight(), _BOX.bottomLeft())


def _swap(painter: QPainter) -> None:
    top, bottom = _BOX.top() + 3, _BOX.bottom() - 3
    painter.drawLine(QPointF(_BOX.left(), top), QPointF(_BOX.right(), top))
    painter.drawLine(QPointF(_BOX.right(), top), QPointF(_BOX.right() - 3.5, top - 3))
    painter.drawLine(QPointF(_BOX.right(), bottom), QPointF(_BOX.left(), bottom))
    painter.drawLine(QPointF(_BOX.left(), bottom), QPointF(_BOX.left() + 3.5, bottom + 3))


def _up_down(painter: QPainter) -> None:
    left, right = _BOX.left() + 3, _BOX.right() - 3
    painter.drawLine(QPointF(left, _BOX.bottom()), QPointF(left, _BOX.top()))
    painter.drawLine(QPointF(left, _BOX.top()), QPointF(left - 3, _BOX.top() + 3.5))
    painter.drawLine(QPointF(right, _BOX.top()), QPointF(right, _BOX.bottom()))
    painter.drawLine(QPointF(right, _BOX.bottom()), QPointF(right + 3, _BOX.bottom() - 3.5))


def _diamond(painter: QPainter) -> None:
    center = _BOX.center()
    radius = _BOX.width() / 2
    painter.drawPolygon(
        [
            QPointF(center.x(), center.y() - radius),
            QPointF(center.x() + radius, center.y()),
            QPointF(center.x(), center.y() + radius),
            QPointF(center.x() - radius, center.y()),
        ]
    )


def _layers(painter: QPainter) -> None:
    for index in range(3):
        y = _BOX.top() + 1 + index * 5
        painter.drawLine(QPointF(_BOX.left(), y), QPointF(_BOX.right(), y))


def _drawers(painter: QPainter) -> None:
    painter.drawRect(_BOX)
    middle = _BOX.center().y()
    painter.drawLine(QPointF(_BOX.left(), middle), QPointF(_BOX.right(), middle))
    painter.drawLine(QPointF(_BOX.center().x() - 1.5, middle - 3), QPointF(_BOX.center().x() + 1.5, middle - 3))
    painter.drawLine(QPointF(_BOX.center().x() - 1.5, middle + 3), QPointF(_BOX.center().x() + 1.5, middle + 3))


def _person(painter: QPainter) -> None:
    head = QRectF(_BOX.center().x() - 3, _BOX.top(), 6, 6)
    painter.drawEllipse(head)
    painter.drawArc(QRectF(_BOX.left(), _BOX.top() + 7, _BOX.width(), _BOX.height()), 0, 180 * 16)


def _people(painter: QPainter) -> None:
    _person(painter)
    painter.drawArc(QRectF(_BOX.left() + 4, _BOX.top() + 1, 11, 6), 30 * 16, 120 * 16)


def _banknote(painter: QPainter) -> None:
    painter.drawRect(QRectF(_BOX.left(), _BOX.top() + 2, _BOX.width(), _BOX.height() - 4))
    painter.drawEllipse(_BOX.center(), 2.4, 2.4)


def _receipt(painter: QPainter) -> None:
    painter.drawRect(QRectF(_BOX.left() + 1.5, _BOX.top(), _BOX.width() - 3, _BOX.height()))
    for index in range(2):
        y = _BOX.top() + 4 + index * 4
        painter.drawLine(QPointF(_BOX.left() + 4, y), QPointF(_BOX.right() - 4, y))


def _ledger(painter: QPainter) -> None:
    """A ruled book: a page with a spine down one side.

    Deliberately not the receipt's plain page — a ledger is the running
    account, not one document, and the two sit close enough in the rail
    that they have to be told apart at a glance.
    """
    painter.drawRect(_BOX)
    spine = _BOX.left() + 3.5
    painter.drawLine(QPointF(spine, _BOX.top()), QPointF(spine, _BOX.bottom()))
    for index in range(3):
        y = _BOX.top() + 3.5 + index * 3.5
        painter.drawLine(QPointF(spine + 2.5, y), QPointF(_BOX.right() - 2, y))


def _tag(painter: QPainter) -> None:
    painter.drawRect(QRectF(_BOX.left(), _BOX.top() + 2.5, _BOX.width() - 2, _BOX.height() - 5))
    painter.drawPoint(QPointF(_BOX.right() - 4, _BOX.center().y()))


def _bars(painter: QPainter) -> None:
    for index, height in enumerate((5.0, 9.5, 7.0)):
        x = _BOX.left() + 1.5 + index * 4.5
        painter.drawLine(QPointF(x, _BOX.bottom()), QPointF(x, _BOX.bottom() - height))


def _sliders(painter: QPainter) -> None:
    for index, knob_x in enumerate((_BOX.left() + 4.5, _BOX.right() - 4.5)):
        y = _BOX.top() + 3.5 + index * 6
        painter.drawLine(QPointF(_BOX.left(), y), QPointF(_BOX.right(), y))
        painter.drawEllipse(QPointF(knob_x, y), 2.0, 2.0)


def _eye(painter: QPainter) -> None:
    """Look at this one.

    An eye is wider than it is tall. Drawn to fill the box in both
    directions it came out round, with a pupil pressed against lids only a
    stroke away on either side — at 14px that reads as a smudge rather
    than as an eye. The lids here span the full width but only a third of
    the height, which leaves the pupil clear air around it.

    A path rather than two arcs: an arc of an ellipse gives a round lens,
    and what reads as an eye is the pointed corners where the lids meet.
    """
    middle = _BOX.center()
    # A quadratic reaches half way to its control point, so the lids open
    # to `_EYE_LIFT / 2` above and below the centre line.
    lift = 7.0
    path = QPainterPath(QPointF(_BOX.left(), middle.y()))
    path.quadTo(QPointF(middle.x(), middle.y() - lift), QPointF(_BOX.right(), middle.y()))
    path.quadTo(QPointF(middle.x(), middle.y() + lift), QPointF(_BOX.left(), middle.y()))
    painter.drawPath(path)
    painter.drawEllipse(middle, 1.5, 1.5)


def _chevron_left(painter: QPainter) -> None:
    """A single chevron pointing at the edge the rail folds towards."""
    x, top, bottom = _BOX.center().x() + 2, _BOX.top() + 2, _BOX.bottom() - 2
    painter.drawPolyline(
        [QPointF(x, top), QPointF(x - 4.5, _BOX.center().y()), QPointF(x, bottom)]
    )


def _chevron_right(painter: QPainter) -> None:
    x, top, bottom = _BOX.center().x() - 2, _BOX.top() + 2, _BOX.bottom() - 2
    painter.drawPolyline(
        [QPointF(x, top), QPointF(x + 4.5, _BOX.center().y()), QPointF(x, bottom)]
    )


_DRAWINGS: dict[str, Callable[[QPainter], None]] = {
    "chevron_left": _chevron_left,
    "chevron_right": _chevron_right,
    "view": _eye,
    "dashboard": _grid,
    "sales": _arrow_up_right,
    "sale_payments": _banknote,
    "payments": _banknote,
    "purchases": _arrow_down_left,
    "purchase_payments": _banknote,
    "payment_methods": _swap,
    "inventory": _layers,
    "cabinets": _drawers,
    "inventory_movement": _up_down,
    "customers": _person,
    "suppliers": _people,
    "ledger": _ledger,
    "customer_ledger": _ledger,
    "supplier_ledger": _ledger,
    "expenses": _receipt,
    "expense_categories": _tag,
    "reports": _bars,
    "company_settings": _sliders,
    "profile": _person,
}


def _screen_ratio() -> float:
    """How many device pixels the display gives a logical one.

    Rarely a whole number: a Windows desktop at 125% reports 1.25. An icon
    drawn at a hardcoded 2x is then resampled by 0.625 to reach the
    screen, and a 1.4px stroke lands across pixel boundaries — which is
    what made the eye look chewed. Drawing at the ratio the display
    actually uses lets every stroke land where it was put.
    """
    app = QGuiApplication.instance()
    screen = app.primaryScreen() if app is not None else None
    return screen.devicePixelRatio() if screen is not None else 1.0


def icon_pixmap(name: str, color: str) -> QPixmap:
    """An icon in `color`. Unknown names render as a diamond."""
    return _rendered(name, color, _screen_ratio())


@lru_cache(maxsize=64)
def _rendered(name: str, color: str, ratio: float) -> QPixmap:
    """Cached because the row-action delegate asks for an icon on every
    repaint of every visible row — painting the same twelve strokes a few
    hundred times a second is the one thing a delegate exists to avoid.
    The set of (name, colour, ratio) an app uses is small and fixed; the
    ratio is a key rather than a constant so moving the window to a second
    monitor redraws rather than rescales."""
    pixmap = QPixmap(round(ICON_SIZE * ratio), round(ICON_SIZE * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(ratio)

    # No manual painter.scale() here: QPainter already maps logical
    # coordinates through the pixmap's device pixel ratio, so scaling again
    # would draw at twice the intended size and clip against the box.
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    pen = QPen(QColor(color))
    pen.setWidthF(_STROKE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    _DRAWINGS.get(name, _diamond)(painter)
    painter.end()

    return pixmap


def nav_icon(name: str, color: str) -> QIcon:
    """The same icon, as a QIcon for a button to wear."""
    return QIcon(icon_pixmap(name, color))
