"""
The Filter choices a document list offers.

Sales, purchases and both payment screens ask the same question of their
rows — how far has this one been paid — so the answer is declared once
here rather than four times.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.presentation.widgets.list_controls import FilterOption

_ZERO = Decimal("0.00")

NOT_FULLY_PAID = "Not fully paid"


def created_at(document) -> datetime:
    """Sort key that never trips over a missing timestamp."""
    return document.created_at or datetime.min


def payment_filters() -> tuple[FilterOption, ...]:
    return (
        FilterOption(NOT_FULLY_PAID, lambda d: d.balance_amount > _ZERO),
        FilterOption("Nothing paid yet", lambda d: d.paid_amount <= _ZERO),
        FilterOption("Part paid", lambda d: _ZERO < d.paid_amount < d.grand_total),
        FilterOption("Fully paid", lambda d: d.balance_amount <= _ZERO),
    )
