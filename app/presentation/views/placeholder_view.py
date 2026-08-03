"""
Stub screen for sidebar routes that don't have a built module yet.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderView(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading = QLabel(title)
        heading.setProperty("role", "pageTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub = QLabel("This module is coming soon.")
        sub.setProperty("role", "pageSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(heading)
        layout.addWidget(sub)
