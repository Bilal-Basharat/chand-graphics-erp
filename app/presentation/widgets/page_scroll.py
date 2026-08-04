"""
The scroller a screen wraps itself in when its content is taller than the
window.

Most screens are one table that stretches to fit whatever height it is
given, and need nothing. A few are a stack of panels at their natural
heights — the dashboard, company settings, reports, my profile — and on a
1366x768 laptop, which is what a shop counter runs, the bottom of those
simply fell off the screen with no way to reach it.

Horizontal scrolling stays off deliberately: the panels inside are happy
to narrow, and a page that slides sideways as well as up loses the reader
their place.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget


def page_scroll(screen: QWidget) -> QWidget:
    """Give `screen` a vertical scroller, and return the body to build in.

    The screen keeps its own layout code — it just puts it inside the
    returned widget rather than directly on itself.
    """
    scroll = QScrollArea(screen)
    scroll.setObjectName("PageScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    body = QWidget()
    body.setObjectName("PageScrollBody")
    scroll.setWidget(body)

    frame = QVBoxLayout(screen)
    frame.setContentsMargins(0, 0, 0, 0)
    frame.addWidget(scroll)
    return body
