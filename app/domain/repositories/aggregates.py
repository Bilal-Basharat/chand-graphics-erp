"""
What an aggregate query answers with, before anyone has named it.

A repository that returns a total returns a `Decimal` and nothing else is
needed. These are for the ones that return several figures at once, where
a tuple would be a set of positions to get wrong.

Primitives only, and no import from the application layer: a port must not
know the shape of the DTO a use case will build out of it. The naming —
"Uncategorised", "Deleted item", the per-cent shares — happens above,
where the words belong.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RevenueTotals:
    """What was invoiced in a period."""

    gross: Decimal
    """Line totals, before any invoice-level discount."""
    discounts: Decimal
    net: Decimal
    """What the customers were actually asked for — gross less discounts."""
    invoice_count: int


@dataclass(frozen=True, slots=True)
class CostTotals:
    """What the stock sold in a period had cost.

    Lines whose cost was never recorded are reported separately rather
    than counted as zero, so a report can say how much of itself it does
    not know.
    """

    cost_of_goods_sold: Decimal
    uncosted_lines: int
    uncosted_revenue: Decimal


@dataclass(frozen=True, slots=True)
class ItemMarginRow:
    """One item's trading in a period, before it is given a name."""

    item_id: int
    quantity_sold: Decimal
    revenue: Decimal
    cost: Decimal
    uncosted_lines: int


@dataclass(frozen=True, slots=True)
class CategorySpendRow:
    """One expense category's spending. A null id is the unfiled bucket."""

    category_id: int | None
    count: int
    total: Decimal


@dataclass(frozen=True, slots=True)
class OutstandingRow:
    """A document with money still on it, whichever side of the shop."""

    reference: str
    party_name: str | None
    """None where the document names no party — a walk-in, or a counter
    purchase."""
    occurred_at: datetime
    outstanding: Decimal
