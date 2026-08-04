"""
KPI tile: label + optional tone-tagged badge, a value, and a note line.
Reused by Dashboard (and future Reports).
"""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

_VALID_TONES = {"success", "info", "warning", "danger"}


class StatTile(QFrame):
    def __init__(
        self,
        label: str,
        value: str,
        note: str = "",
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
        self._label_widget = QLabel(label.upper())
        self._label_widget.setProperty("role", "statLabel")
        top_row.addWidget(self._label_widget)
        top_row.addStretch(1)

        if tag_text:
            tone = tag_tone if tag_tone in _VALID_TONES else "info"
            tag = QLabel(tag_text)
            tag.setProperty("role", "tag")
            tag.setProperty("tone", tone)
            top_row.addWidget(tag)

        self._value_label = QLabel(value)
        self._value_label.setProperty("role", "statValue")

        self._note_label = QLabel(note)
        self._note_label.setProperty("role", "statNote")

        outer.addLayout(top_row)
        outer.addWidget(self._value_label)
        outer.addWidget(self._note_label)

    def set_label(self, label: str) -> None:
        """Uppercased here as at construction, so callers pass ordinary
        words and the tiles stay typographically identical."""
        self._label_widget.setText(label.upper())

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)

    def set_note(self, note: str) -> None:
        self._note_label.setText(note)
