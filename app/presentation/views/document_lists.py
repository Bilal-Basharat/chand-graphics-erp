"""
The Filter choices a document list offers.

Sales, purchases and both payment screens ask the same question of their
rows — how far has this one been paid — so the answer is declared once
here rather than four times.
"""
from __future__ import annotations

from datetime import datetime

from app.domain.enums.payment_filter import PaymentFilter
from app.presentation.widgets.list_controls import FilterOption

NOT_FULLY_PAID = "Not fully paid"


def created_at(document) -> datetime:
    """Sort key that never trips over a missing timestamp."""
    return document.created_at or datetime.min


def payment_filters() -> tuple[FilterOption, ...]:
    return (
        FilterOption(NOT_FULLY_PAID, PaymentFilter.NOT_FULLY_PAID),
        FilterOption("Nothing paid yet", PaymentFilter.NOTHING_PAID),
        FilterOption("Part paid", PaymentFilter.PART_PAID),
        FilterOption("Fully paid", PaymentFilter.FULLY_PAID),
    )
