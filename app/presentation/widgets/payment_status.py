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


def payment_status_text(document) -> str:
    if document.balance_amount <= _ZERO:
        return "Paid"
    if document.paid_amount > _ZERO:
        return "Part paid"
    return "Unpaid"


def payment_status_color(document) -> str:
    if document.balance_amount <= _ZERO:
        return t.SUCCESS
    if document.paid_amount > _ZERO:
        return t.WARNING
    return t.DANGER
