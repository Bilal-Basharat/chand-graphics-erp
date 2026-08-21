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

CURRENCY = "PKR"
"""The currency every figure is in.

Named once so a tile that sets it beside its value and a line that
appends it to a figure cannot end up disagreeing.
"""

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

CASH = "Cash"
"""How a payment reads when it names no method.

Money over the counter is the default in this shop, and it is what a
payment with nothing recorded against it was. Naming it here rather than
seeding a row means an installation starts with an empty methods list and
still records payments correctly — the ones the owner adds are for the
exceptions.
"""


def money(value: Decimal | int | float | None) -> str:
    """Thousands-separated, always two decimals. `None` renders as a dash."""
    if value is None:
        return DASH
    return f"{Decimal(value):,.2f}"


def percent(value: Decimal | None) -> str:
    """A margin, or a dash where there is nothing to take a share of."""
    return DASH if value is None else f"{value}%"


def uncosted_caveat(lines: int, revenue: Decimal) -> str:
    """What a profit figure does not know, or "" when it knows everything.

    Said in one place because it is said in two: on the screen under the
    tiles, and in the note on the printed statement. Two wordings of the
    same warning is one of them going stale.
    """
    if not lines:
        return ""
    return (
        f"{counted(lines, 'sale line')} had no recorded cost "
        f"({money(revenue)} of revenue). Profit is overstated by whatever that "
        f"stock cost — record a purchase for the item to fix it."
    )


def money_or_blank(value: Decimal | int | float) -> str:
    """A figure, or nothing at all when there isn't one.

    For a pair of columns where each row fills exactly one — a ledger's
    debit and credit. A column of "0.00"s beside the figures that matter
    reads as data; a blank reads as "not this one", which is what it is.
    Distinct from `money(None)`, which is a dash: that says the value is
    unknown, this says it does not apply.
    """
    return money(value) if value else ""


def whole_money(value: Decimal | int | float) -> str:
    """A headline figure, uncurrencied: "12,500".

    Whole rupees — for tiles and summaries, where the number stands alone
    and paisa would be noise. Table cells keep `money()`: there the
    decimals line up down the column.
    """
    return f"{Decimal(value):,.0f}"


def pkr(value: Decimal | int | float) -> str:
    """A headline figure with its currency after it: "12,500 PKR".

    The unit trails the number, as it is spoken and as a tile shows it,
    so the figure itself is what the eye lands on first.
    """
    return f"{whole_money(value)} {CURRENCY}"


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


def payment_method_name(name: str | None) -> str:
    """How a payment was settled, for a name that may not be there.

    Covers both ways that happens: nothing was chosen when the payment was
    recorded, and the method it named was deleted afterwards. Neither is
    missing data, so neither renders as a dash.
    """
    return name or CASH


def quantity(count: int, unit: str | None) -> str:
    """"500 sheets", "2 bottles", or plain "500" when nothing names it."""
    return f"{count} {unit}" if unit else str(count)

