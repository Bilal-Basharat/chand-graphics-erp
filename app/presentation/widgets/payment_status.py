"""
How far a sale or a purchase has been settled.

Sales, purchases and both payment screens all answer this question, and
they have to answer it with the same three words and the same three
colours — a purchase that reads "Part paid" on one screen and "Partial"
on the next reads as two different states.
"""
from __future__ import annotations

from decimal import Decimal

from app.presentation.theme import tokens as t

_ZERO = Decimal("0.00")

STATUS_COLORS: dict[str, str] = {
    "Paid": t.SUCCESS,
    "Part paid": t.WARNING,
    "Unpaid": t.DANGER,
}
"""The three words and the three colours, paired once.

Exported for the screens that hold a status already worked out rather
than the document it came from — the dashboard summarises its rows before
it draws them. Anything with the document itself should call the two
functions below instead of reaching in here.
"""


def payment_status_text(document) -> str:
    if document.balance_amount <= _ZERO:
        return "Paid"
    if document.paid_amount > _ZERO:
        return "Part paid"
    return "Unpaid"


def payment_status_color(document) -> str:
    return STATUS_COLORS[payment_status_text(document)]
