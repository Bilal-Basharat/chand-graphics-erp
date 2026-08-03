"""
Add or edit one line of a sale or purchase.

Quantity and unit price sit side by side with a running line total beneath
them, because the number the user is actually deciding is the total — the
two inputs are just how they get there. Previously a sale asked only for a
price and silently assumed a quantity of one.
"""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.formatting import money
from app.presentation.theme import tokens as t
from app.presentation.widgets.document_lines import ZERO, parse_amount
from app.presentation.widgets.modern_spinbox import ModernSpinBox

MAX_QUANTITY = 1_000_000


class LineItemDialog(FormDialog):
    """Returns `(quantity, unit_price)` via `build_command()`."""

    def __init__(
        self,
        *,
        item_label: str,
        title: str = "Add item",
        submit_label: str = "Add to sale",
        quantity: int = 1,
        unit_price: Decimal | None = None,
        available_stock: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title=title,
            subtitle=item_label,
            submit_label=submit_label,
            parent=parent,
        )
        self._available_stock = available_stock

        self._quantity = ModernSpinBox()
        self._quantity.setRange(1, MAX_QUANTITY)
        self._quantity.setValue(quantity)
        self._quantity.valueChanged.connect(self._update_line_total)

        self._unit_price = QLineEdit("" if unit_price is None else f"{unit_price:.2f}")
        self._unit_price.setPlaceholderText("0.00")
        self._unit_price.textChanged.connect(self._update_line_total)

        # One row: the two figures are read together, and stacking them
        # hides the relationship between them.
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)
        row_layout.addLayout(_field("Quantity", self._quantity))
        row_layout.addLayout(_field("Unit price", self._unit_price), 1)
        self._form.addRow(row)

        self._line_total = QLabel(money(ZERO))
        self._line_total.setStyleSheet(
            f"color: {t.INK}; font-size: 17px; font-weight: {t.WEIGHT_SEMIBOLD};"
        )
        self.add_row("Line total", self._line_total)

        if available_stock is not None:
            hint = QLabel(f"{available_stock} in stock")
            hint.setProperty("role", "fieldHelp")
            self.add_row("", hint)

        self._update_line_total()
        self._unit_price.setFocus()

    def _update_line_total(self) -> None:
        price = parse_amount(self._unit_price.text()) or ZERO
        self._line_total.setText(money(max(price, ZERO) * self._quantity.value()))

    def build_command(self) -> tuple[int, Decimal] | None:
        price = parse_amount(self._unit_price.text())
        if price is None or price < ZERO:
            self.reject_with("Enter a unit price.", self._unit_price)
            return None

        quantity = self._quantity.value()
        if self._available_stock is not None and quantity > self._available_stock:
            self.reject_with(
                f"Only {self._available_stock} in stock.",
                self._quantity,
            )
            return None

        return quantity, price

    def submit_command(self, command: tuple[int, Decimal]) -> None:
        # Nothing to persist: the caller reads `result` after exec().
        self._result = command
        self.accept()

    def line(self) -> tuple[int, Decimal] | None:
        """The accepted (quantity, unit price), or None if cancelled."""
        return getattr(self, "_result", None)


def _field(label_text: str, field: QWidget) -> QVBoxLayout:
    block = QVBoxLayout()
    block.setSpacing(5)
    label = QLabel(label_text)
    label.setProperty("role", "fieldLabel")
    block.addWidget(label)
    block.addWidget(field)
    return block
