"""
A control with its label above it.

The unit every form row in the app is built from. It lives here rather
than with the dialogs so that a widget which *is* a row of fields — see
`item_picker_row.py` — can be built from the same piece, instead of a
widget reaching up into the dialog that happens to host it.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def field(label_text: str, widget: QWidget) -> QVBoxLayout:
    """A labelled control. A blank label keeps a control's baseline level
    with its labelled neighbours in the same row."""
    block = QVBoxLayout()
    block.setSpacing(5)
    label = QLabel(label_text or " ")
    label.setProperty("role", "fieldLabel")
    block.addWidget(label)
    block.addWidget(widget)
    return block
