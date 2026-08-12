from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class SearchQuery:
    term: str
    limit: int = 50


@dataclass(slots=True)
class LedgerQuery:
    party_id: int
    start: datetime
    end: datetime
    limit: int = 500


@dataclass(frozen=True, slots=True)
class LedgerLine:
    """One row of a party's statement, with the balance it left behind.

    `charge` and `payment` are named for what they do to the balance, not
    for an accounting side: the same line is a debit on a customer's
    statement and a credit on a supplier's. Only one of the two is ever
    non-zero.
    """

    occurred_at: datetime
    reference: str
    detail: str
    document_kind: str
    """Which family of document this line came from, so a screen can open
    it. Set by the source that produced it — see
    `app.application.ledger.sources`."""
    charge: Decimal
    payment: Decimal
    balance: Decimal


@dataclass(frozen=True, slots=True)
class PartyLedger:
    """A customer's or supplier's account over one period."""

    party_id: int
    party_name: str
    opening_balance: Decimal
    """As at the start of the period — the party's own opening balance
    plus everything that happened before it."""
    lines: tuple[LedgerLine, ...]
    total_charges: Decimal
    total_payments: Decimal
    closing_balance: Decimal
    """What is outstanding at the end. Positive means the party owes:
    money to collect on a customer's ledger, money to pay on a
    supplier's."""


@dataclass(frozen=True, slots=True)
class ReportQuery:
    """A period to report on.

    Deliberately not `DateRangeQuery`: that carries a `limit`, and a
    report that answers about the first N documents is not a report. Every
    query behind these counts everything in the window.
    """

    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class AgeingQuery:
    """A moment to age unpaid documents against — usually now."""

    as_at: datetime


@dataclass(frozen=True, slots=True)
class CategorySpend:
    """One line of the spending breakdown."""

    name: str
    count: int
    total: Decimal
    share: Decimal
    """Per cent of the period's spending. Computed once, where the
    denominator is known, so screen and paper cannot work it out
    differently."""


@dataclass(frozen=True, slots=True)
class ProfitAndLoss:
    """Whether the shop made money in a period, and where it went.

    Revenue less what the stock cost is gross profit; less what was spent
    running the place is net profit. Purchases are *not* in that
    arithmetic — buying stock is not a cost until the stock is sold, which
    is the whole difference between this and the "money in, money out"
    figure it replaces. `stock_bought` is carried alongside as context
    only.
    """

    start: datetime
    end: datetime

    invoice_count: int
    gross_revenue: Decimal
    invoice_discounts: Decimal
    revenue: Decimal

    cost_of_goods_sold: Decimal
    expenses_total: Decimal
    expense_count: int
    spending: tuple[CategorySpend, ...]

    uncosted_lines: int
    """Sale lines whose stock had no recorded cost. Their revenue is in
    the figures above; their cost is not, because nobody knows it."""
    uncosted_revenue: Decimal

    stock_bought: Decimal
    """What was spent on stock in the period. Context, not a cost of it."""

    @property
    def gross_profit(self) -> Decimal:
        return self.revenue - self.cost_of_goods_sold

    @property
    def net_profit(self) -> Decimal:
        return self.gross_profit - self.expenses_total

    @property
    def gross_margin(self) -> Decimal | None:
        """Gross profit as a percentage of revenue, or None if nothing sold.

        None rather than zero: no sales is no answer, and a nought would
        read as "sold at cost".
        """
        return _percent_of(self.gross_profit, self.revenue)

    @property
    def net_margin(self) -> Decimal | None:
        return _percent_of(self.net_profit, self.revenue)

    @property
    def is_complete(self) -> bool:
        """Whether every line sold in the period knew what it had cost."""
        return self.uncosted_lines == 0


@dataclass(frozen=True, slots=True)
class ItemMargin:
    """What one item earned in a period."""

    item_id: int
    name: str
    quantity_sold: int
    revenue: Decimal
    """Line totals. Invoice-level discounts are not apportioned to items,
    so this runs slightly ahead of the revenue on the profit & loss."""
    cost: Decimal | None
    """None when nothing sold of it had a recorded cost."""
    uncosted_lines: int

    @property
    def profit(self) -> Decimal | None:
        return None if self.cost is None else self.revenue - self.cost

    @property
    def margin(self) -> Decimal | None:
        profit = self.profit
        return None if profit is None else _percent_of(profit, self.revenue)


@dataclass(frozen=True, slots=True)
class ItemProfitability:
    """Every item sold in a period, best earner first."""

    start: datetime
    end: datetime
    rows: tuple[ItemMargin, ...]
    revenue: Decimal
    cost: Decimal
    uncosted_lines: int

    @property
    def profit(self) -> Decimal:
        return self.revenue - self.cost

    @property
    def margin(self) -> Decimal | None:
        return _percent_of(self.profit, self.revenue)


@dataclass(frozen=True, slots=True)
class AgeingBand:
    """How much money has been outstanding for roughly this long."""

    label: str
    count: int
    total: Decimal
    share: Decimal


@dataclass(frozen=True, slots=True)
class AgeingLine:
    """One unpaid document, and how long it has been that way."""

    party: str
    reference: str
    occurred_at: datetime
    age_days: int
    band: str
    outstanding: Decimal


@dataclass(frozen=True, slots=True)
class Ageing:
    """What is owed, sorted by how long it has been owed.

    Aged from the day each document was raised. Nothing in this app
    records payment terms, so "overdue" is a question it cannot honestly
    answer — only "how old".
    """

    as_at: datetime
    bands: tuple[AgeingBand, ...]
    """Always every band, zeros included, so the strip along the top keeps
    its shape whatever is outstanding."""
    lines: tuple[AgeingLine, ...]
    total: Decimal


def _percent_of(part: Decimal, whole: Decimal) -> Decimal | None:
    """`part` as a percentage of `whole`, or None when there is no whole."""
    if whole == 0:
        return None
    return (part * Decimal(100) / whole).quantize(Decimal("0.1"))


@dataclass(slots=True)
class PurchasePaymentStatus:
    purchase_id: int
    grand_total: Decimal
    paid_amount: Decimal
    balance_amount: Decimal


@dataclass(slots=True)
class SalePaymentStatus:
    sale_id: int
    grand_total: Decimal
    paid_amount: Decimal
    balance_amount: Decimal