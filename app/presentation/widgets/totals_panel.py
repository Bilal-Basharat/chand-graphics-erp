"""
The money block at the foot of a sale or purchase: discount, payment, and
the resulting totals.

Shared because the arithmetic and the wording have to agree across both
documents — a "balance due" that means one thing on a sale and another on
a purchase is exactly the kind of vagueness that makes a total untrusted.
"""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.presentation.formatting import money
from app.presentation.theme import tokens as t
from app.presentation.widgets.document_lines import (
    ZERO,
    DocumentLine,
    DocumentTotals,
    compute_totals,
    parse_amount_or_zero,
)
from app.presentation.widgets.payment_method_combo import PaymentMethodCombo

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class TotalsPanel(QWidget):
    changed = Signal()

    def __init__(self, *, paid_caption: str = "Paid now", parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        inputs = QGridLayout()
        inputs.setHorizontalSpacing(14)
        inputs.setVerticalSpacing(6)

        self._discount = QLineEdit("0")
        self._discount.setPlaceholderText("0.00")
        # textChanged carries the new text; `changed` carries nothing. Wired
        # directly, Qt raises inside the slot and the totals silently stop
        # updating as the user types.
        self._discount.textChanged.connect(lambda _text: self.changed.emit())

        self._payment_method = PaymentMethodCombo()

        self._paid = QLineEdit("0")
        self._paid.setPlaceholderText("0.00")
        self._paid.textChanged.connect(lambda _text: self.changed.emit())

        for column, (caption, field) in enumerate(
            [
                ("Discount", self._discount),
                ("Payment method", self._payment_method),
                (paid_caption, self._paid),
            ]
        ):
            label = QLabel(caption)
            label.setProperty("role", "fieldLabel")
            inputs.addWidget(label, 0, column)
            inputs.addWidget(field, 1, column)
            inputs.setColumnStretch(column, 1)
        outer.addLayout(inputs)

        totals_row = QHBoxLayout()
        totals_row.setSpacing(28)
        # The figures sit against the right edge, under the amount columns
        # of the line table above them — that is where the eye already is
        # after reading a column of line totals, and where every printed
        # invoice puts them.
        totals_row.addStretch(1)
        self._subtotal_label = _figure(t.MUTED)
        self._total_label = _figure(t.INK, size=18)
        self._balance_label = _figure(t.DANGER)
        for caption, value in [
            ("Subtotal", self._subtotal_label),
            ("Total", self._total_label),
            # "Left to pay" rather than "Balance due": the same words this
            # shop's staff would use out loud, and the same ones the
            # payment screens use for the identical figure.
            ("Left to pay", self._balance_label),
        ]:
            block = QVBoxLayout()
            block.setSpacing(2)
            label = QLabel(caption)
            label.setProperty("role", "statLabel")
            label.setAlignment(_RIGHT)
            value.setAlignment(_RIGHT)
            block.addWidget(label)
            block.addWidget(value)
            totals_row.addLayout(block)
        outer.addLayout(totals_row)

    # ---------------- inputs ----------------

    def set_payment_methods(self, methods: list) -> None:
        self._payment_method.set_methods(methods)

    @property
    def discount(self) -> Decimal:
        return parse_amount_or_zero(self._discount.text())

    @property
    def paid(self) -> Decimal:
        return parse_amount_or_zero(self._paid.text())

    @property
    def payment_method_id(self) -> int | None:
        return self._payment_method.method_id

    def focus_discount(self) -> None:
        self._discount.setFocus()
        self._discount.selectAll()

    def focus_paid(self) -> None:
        self._paid.setFocus()
        self._paid.selectAll()

    # ---------------- output ----------------

    def render(self, lines: list[DocumentLine]) -> DocumentTotals:
        """Recompute from the current lines and inputs, and show the result."""
        totals = compute_totals(lines, self.discount, self.paid)
        self._subtotal_label.setText(money(totals.subtotal))
        self._total_label.setText(money(totals.grand_total))
        self._balance_label.setText(money(totals.balance))
        # Nothing owing reads as settled, not as an outstanding zero.
        self._balance_label.setStyleSheet(
            f"color: {t.SUCCESS if totals.balance <= ZERO else t.DANGER};"
            f" font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 14px;"
        )
        return totals


def _figure(color: str, size: int = 14) -> QLabel:
    label = QLabel(money(ZERO))
    label.setStyleSheet(f"color: {color}; font-weight: {t.WEIGHT_SEMIBOLD}; font-size: {size}px;")
    return label
