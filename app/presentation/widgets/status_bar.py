"""
Thin bottom status strip: where you are on the left, what the app is on
the right.

The right-hand side is handed its text rather than reading the settings
itself — a widget that imports configuration is a widget you cannot put
on screen without an environment behind it.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.presentation.theme import tokens as t


SEPARATOR = "   •   "


class AppStatusBar(QWidget):
    def __init__(
        self,
        app_version: str,
        developed_by: str,
        parent: QWidget | None = None,
    ) -> None:
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

        about = QLabel(
            SEPARATOR.join(
                ["Local database", f"v{app_version}", f"Developed by {developed_by}"]
            )
        )
        about.setStyleSheet(f"color: {t.MUTED}; font-size: 11px;")
        layout.addWidget(about)

    def set_page(self, page_name: str, hint: str = "") -> None:
        """`hint` is whatever is true of the *current* screen — the shortcut
        line used to name one module regardless of where you actually were."""
        self._label.setText(f"{page_name}{SEPARATOR}{hint}" if hint else page_name)
