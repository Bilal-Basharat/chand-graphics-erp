"""
Small colored status label for table rows (e.g. card stock status).
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel

_VALID_TONES = {"ok", "low", "out"}


class StatusPill(QLabel):
    def __init__(self, text: str, tone: str = "ok", parent=None) -> None:
        super().__init__(text, parent)
        self.setProperty("role", "pill")
        self.setProperty("tone", tone if tone in _VALID_TONES else "ok")
