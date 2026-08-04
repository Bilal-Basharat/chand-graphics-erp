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

TO_COLLECT = "To collect from customers"
TO_PAY = "To pay suppliers"

TO_COLLECT_SHORT = "to collect"
TO_PAY_SHORT = "to pay"
"""The same two things, for where they sit beside their own figure and
the full phrase would not fit."""

SETTLED = "Nothing outstanding"
"""The two directions money can still be owed in, and neither.

Shared so the dashboard and the reports screen name the same thing the
same way. Written as what is left to do rather than as "owes" — the
person reading it wants to know who has to act, and on which side.
"""

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


def counted(count: int, singular: str, plural: str | None = None) -> str:
    """"3 invoices", "1 invoice".

    Only the regular -s plural is derived; an irregular one names itself.
    Worth the helper because narrow periods routinely produce a count of
    one, and "1 invoices" reads as a bug in the figure beside it.
    """
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"


def or_dash(value) -> str:
    return str(value) if value not in (None, "") else DASH


def card_label(card) -> str:
    """How a wedding card names itself in pickers and line items."""
    return f"{card.card_number} — {card.name}" if card.name else card.card_number
