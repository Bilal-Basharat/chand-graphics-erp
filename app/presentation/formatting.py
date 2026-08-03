"""
Display formatting shared across screens.

Money and dates appear in almost every table and total row, and they have
to look the same in all of them — a purchase total formatted one way on
the purchases list and another on the dashboard reads as two different
numbers.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

DASH = "—"

WALK_IN = "Walk-in customer"
NO_SUPPLIER = "No supplier"
"""What a document with no party attached says instead of nothing.

A blank cell reads as missing data — as though the name failed to load.
These are facts about the document: nobody was named, because nobody
needed to be.
"""


def money(value: Decimal | int | float | None) -> str:
    """Thousands-separated, always two decimals. `None` renders as a dash."""
    if value is None:
        return DASH
    return f"{Decimal(value):,.2f}"


def date_time(value: datetime | None) -> str:
    if value is None:
        return DASH
    return f"{value:%d %b %Y, %H:%M}"


def date_only(value: datetime | None) -> str:
    if value is None:
        return DASH
    return f"{value:%d %b %Y}"


def or_dash(value) -> str:
    return str(value) if value not in (None, "") else DASH


def card_label(card) -> str:
    """How a wedding card names itself in pickers and line items."""
    return f"{card.card_number} — {card.name}" if card.name else card.card_number
