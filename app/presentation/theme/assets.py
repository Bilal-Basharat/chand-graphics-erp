"""
Small image assets the stylesheet needs as files.

QSS can only reference an image by URL, so the handful of marks that have
to be *drawn* (rather than described in QSS) are painted once with
QPainter and cached on disk. That beats the alternatives: shipping binary
PNGs in the repo, or compiling a .qrc resource file as a build step.

Only the checkbox tick needs this today. Styling `QCheckBox::indicator`
replaces the style's own painting wholesale — including the tick — so a
checked box would otherwise render as a plain filled square.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

from app.config.paths import DATA_DIR
from app.presentation.theme import tokens as t

logger = logging.getLogger(__name__)

_ASSET_DIR = DATA_DIR / "ui"
_TICK_SIZE = 16
_CHEVRON_SIZE = 10
_CHEVRON_COLOR = t.MUTED
_SCALE = 2  # painted at 2x so it stays crisp on scaled displays


def _paint_tick(path: Path) -> None:
    pixmap = QPixmap(_TICK_SIZE * _SCALE, _TICK_SIZE * _SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(Qt.GlobalColor.white)
    pen.setWidthF(2.2 * _SCALE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(
        [
            QPointF(4.0 * _SCALE, 8.5 * _SCALE),
            QPointF(6.8 * _SCALE, 11.3 * _SCALE),
            QPointF(12.0 * _SCALE, 5.2 * _SCALE),
        ]
    )
    painter.end()

    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")


def _paint_chevron(path: Path) -> None:
    """The combo box's own drop-down mark.

    Styling `QComboBox::drop-down` replaces the style's arrow with
    nothing, so without this a combo has no mark at all — and the native
    one, where it survives, is a dated 3D triangle that ignores the rest
    of the theme.
    """
    size = _CHEVRON_SIZE * _SCALE
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(_CHEVRON_COLOR))
    pen.setWidthF(1.6 * _SCALE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(
        [
            QPointF(2.5 * _SCALE, 4.0 * _SCALE),
            QPointF(5.0 * _SCALE, 6.8 * _SCALE),
            QPointF(7.5 * _SCALE, 4.0 * _SCALE),
        ]
    )
    painter.end()

    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")


def combo_chevron_url() -> str:
    """A QSS-usable url() path to the combo box drop-down chevron."""
    return _asset_url("combo-chevron.png", _paint_chevron)


def checkbox_tick_url() -> str:
    """A QSS-usable url() path to the white checkbox tick.

    Returns an empty string if the asset can't be written, so the caller
    can omit the rule rather than emit a url() pointing at nothing.
    """
    return _asset_url("checkbox-tick.png", _paint_tick)


def _asset_url(name: str, paint) -> str:
    """Paint `name` once, and hand back a path QSS can use.

    Returns an empty string if the asset can't be written, so the caller
    can omit the rule rather than emit a url() pointing at nothing.
    """
    path = _ASSET_DIR / name
    try:
        if not path.exists():
            paint(path)
    except OSError:
        logger.exception("Could not write the %s asset", name)
        return ""
    # QSS wants forward slashes on every platform.
    return path.as_posix()
