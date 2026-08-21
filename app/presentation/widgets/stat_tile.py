"""
KPI tile: label + optional tone-tagged badge, a value with an optional
unit after it, and a note line.
Reused by Dashboard (and future Reports).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

_VALID_TONES = {"success", "info", "warning", "danger"}


class StatTile(QFrame):
    def __init__(
        self,
        label: str,
        value: str,
        note: str = "",
        unit: str = "",
        tag_text: str | None = None,
        tag_tone: str = "info",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "statTile")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(5)

        top_row = QHBoxLayout()
        label_widget = QLabel(label.upper())
        label_widget.setProperty("role", "statLabel")
        top_row.addWidget(label_widget)
        top_row.addStretch(1)

        if tag_text:
            tone = tag_tone if tag_tone in _VALID_TONES else "info"
            tag = QLabel(tag_text)
            tag.setProperty("role", "tag")
            tag.setProperty("tone", tone)
            top_row.addWidget(tag)

        self._value_label = QLabel(value)
        self._value_label.setProperty("role", "statValue")

        value_row = QHBoxLayout()
        value_row.setSpacing(5)
        value_row.addWidget(self._value_label)
        if unit:
            # Small, and after the figure rather than before it: every
            # money tile carries the same unit, so it is the number that
            # is being scanned for and the number that should be read
            # first. Sat on the baseline so it reads as part of the value.
            unit_label = QLabel(unit)
            unit_label.setProperty("role", "statUnit")
            value_row.addWidget(unit_label, alignment=Qt.AlignmentFlag.AlignBottom)
        value_row.addStretch(1)

        self._note_label = QLabel(note)
        self._note_label.setProperty("role", "statNote")

        outer.addLayout(top_row)
        outer.addLayout(value_row)
        outer.addWidget(self._note_label)

    def set_value(self, value: str, color: str = "") -> None:
        """The figure, and the colour it is to be read in.

        Left to the caller because the same number means opposite things
        on different tiles — no sales is a bad month, no low-stock items
        is a full shelf — and only the screen knows which it is showing.
        No colour returns the figure to the tile's ordinary ink.
        """
        self._value_label.setText(value)
        self._value_label.setStyleSheet(f"color: {color};" if color else "")

    def set_note(self, note: str) -> None:
        self._note_label.setText(note)
