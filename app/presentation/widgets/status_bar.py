"""
Thin bottom status strip: current page name + keyboard shortcut hints.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.presentation.theme import tokens as t


class AppStatusBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBar")
        # Required for the #StatusBar rule's background to be painted at
        # all — see the note in theme/stylesheet.py.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(t.STATUSBAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        self._label = QLabel("")
        self._label.setStyleSheet(f"color: {t.MUTED}; font-size: 11px;")
        layout.addWidget(self._label)
        layout.addStretch(1)

        hint = QLabel("Local database")
        hint.setStyleSheet(f"color: {t.MUTED}; font-size: 11px;")
        layout.addWidget(hint)

    def set_page(self, page_name: str, hint: str = "") -> None:
        """`hint` is whatever is true of the *current* screen — the shortcut
        line used to name one module regardless of where you actually were."""
        self._label.setText(f"{page_name}   •   {hint}" if hint else page_name)
