"""
The app's one destructive-action confirmation.

`QMessageBox.question` defaults to Yes/No — or worse, Yes/Cancel, which
asks the user to press "Cancel" to *not* cancel something. Both make the
reader translate a generic word back into the action they just asked for.

Here the confirming button says what it does ("Discard sale", "Delete
customer") and the other one says "Keep". The safe choice is the default,
so Enter and Escape both back out.
"""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def confirm_destructive(
    parent: QWidget,
    *,
    title: str,
    message: str,
    confirm_label: str,
    cancel_label: str = "Keep",
) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(message)

    confirm = box.addButton(confirm_label, QMessageBox.ButtonRole.DestructiveRole)
    keep = box.addButton(cancel_label, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(keep)
    box.setEscapeButton(keep)

    box.exec()
    return box.clickedButton() is confirm
