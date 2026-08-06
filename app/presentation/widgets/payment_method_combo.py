"""
"How was this settled?" picker, shared by the screens that record money.

Cash is the first entry and the one it opens on, because that is what
almost every counter sale and small purchase is settled in. It records no
method at all rather than pointing at a row — see
`presentation.formatting.CASH` — so an installation works out of the box
with an empty payment-methods list, and the methods the owner adds are
for the exceptions.

A method the owner happens to have named "Cash" is left out of the list:
it means the same thing as the entry already at the top, and two
identical lines in a dropdown read as a bug.
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QWidget

from app.presentation.formatting import CASH


class PaymentMethodCombo(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.set_methods([])

    def set_methods(self, methods: list) -> None:
        self.clear()
        self.addItem(CASH, None)
        for method in methods:
            if method.name.strip().casefold() != CASH.casefold():
                self.addItem(method.name, method.id)
        self.setCurrentIndex(0)

    @property
    def method_id(self) -> int | None:
        """The chosen method, or None for cash."""
        return self.currentData()
