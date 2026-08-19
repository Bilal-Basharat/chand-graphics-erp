from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Generic, TypeVar

from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.domain.enums.payment_filter import PaymentFilter
from app.domain.enums.stock_filter import StockFilter

RowT = TypeVar("RowT")


# ------------------------------------------------------------------ paging

# What a list screen asks for, and what it gets back. One pair for every
# list in the application, because every list asks the same five things —
# which page, how big, what was typed, sorted by what, which way — and
# only then differs by what it is a list *of*.
#
# The screen never sees a whole table. That is not a performance tuning:
# a shop with two thousand items had no way to reach the last thousand of
# them, and the screen said nothing about it.

DEFAULT_PAGE_SIZE = 100
"""Enough that most lists are one page, small enough to stay quick."""

MAX_PAGE_SIZE = 500
"""The most that may be asked for at once, whatever the caller says. A
page is a screenful to read, not a way to ask for the table back."""


@dataclass(slots=True, kw_only=True)
class PageQuery:
    """One page of a list, as the screen asks for it.

    Keyword-only so the screens that add filters of their own — a date
    range, a stock level — can subclass this without their fields having
    to be ordered around these.
    """

    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    search: str = ""
    sort_field: str | None = None
    """None asks for the list's own default order. Whether a field can be
    sorted on at all is the repository's to say, not the caller's."""
    sort_desc: bool = False

    def __post_init__(self) -> None:
        # Clamped here rather than at each of the call sites, because a
        # page number arrives from a button, a query string or a test and
        # only one of those three can be trusted to be sane.
        self.page = max(1, self.page)
        self.page_size = min(max(1, self.page_size), MAX_PAGE_SIZE)
        self.search = self.search.strip()

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class PageTotals:
    """What a list adds up to over the whole filtered set, not this page.

    The summary strips on the document screens are answers about a period
    — "sold this month" — so they cannot be added up from the rows in
    hand. Carried beside the page rather than fetched separately so the
    figures and the rows can never be from different moments.
    """

    total: Decimal
    outstanding: Decimal


@dataclass(frozen=True, slots=True)
class PageResult(Generic[RowT]):
    """A page of rows, and where it sits in the whole."""

    rows: list[RowT]
    total: int
    """Every row the query matched, not the length of `rows`."""
    page: int
    page_size: int
    totals: PageTotals | None = None
    """Only where a screen shows a summary strip."""

    # Derived rather than stored: a `has_next` that could disagree with
    # the three numbers it is drawn from is a bug waiting to be shipped.

    @property
    def page_count(self) -> int:
        if self.total <= 0:
            return 1
        return -(-self.total // self.page_size)

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.page_count

    @property
    def first_index(self) -> int:
        """The position of the first row on this page, counting from one."""
        return 0 if not self.rows else (self.page - 1) * self.page_size + 1

    @property
    def last_index(self) -> int:
        return 0 if not self.rows else self.first_index + len(self.rows) - 1

    @classmethod
    def empty(cls, query: PageQuery) -> PageResult[RowT]:
        return cls(rows=[], total=0, page=query.page, page_size=query.page_size)


@dataclass(slots=True, kw_only=True)
class InventoryPageQuery(PageQuery):
    stock: StockFilter | None = None


@dataclass(slots=True, kw_only=True)
class DocumentPageQuery(PageQuery):
    """A page of sales or of purchases: a period, and how far paid."""

    start: datetime
    end: datetime
    payment: PaymentFilter | None = None


@dataclass(slots=True, kw_only=True)
class PaymentPageQuery(PageQuery):
    """A page of the documents a payment screen collects against."""

    start: datetime
    end: datetime
    payment: PaymentFilter | None = None


@dataclass(slots=True, kw_only=True)
class ExpensePageQuery(PageQuery):
    start: datetime
    end: datetime
    category_id: int | None = None
    uncategorised: bool = False
    """Its own flag rather than a category id of None, which already means
    "every category" — an expense filed under nothing is a choice a screen
    offers, and the two cannot share one field."""


@dataclass(slots=True, kw_only=True)
class MovementPageQuery(PageQuery):
    inventory_item_id: int | None = None
    """Which item's history to read, or None for the whole register.

    Optional because the screen answers two questions: "what has moved
    lately?" and "why is this item's count what it is?".
    """

    movement_type: MovementType | None = None


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

@dataclass(frozen=True, slots=True)
class ReturnableLine:
    """One line of a document, and how much of it can still come back."""

    line_id: int
    item_type: ItemType
    inventory_item_id: int | None
    label: str
    quantity: int
    returned: int
    unit_price: Decimal

    @property
    def remaining(self) -> int:
        return self.quantity - self.returned

    @property
    def is_returnable(self) -> bool:
        return self.remaining > 0


@dataclass(frozen=True, slots=True)
class ReturnableDocument:
    """A sale or a purchase, as the return dialog needs to see it.

    One shape for both, because a return dialog differs between them only
    in the noun it uses. `refundable` is the most that can honestly be
    handed back: money that came in and has not already gone out again.
    """

    document_id: int
    reference: str
    party_id: int | None
    party_name: str
    lines: tuple[ReturnableLine, ...]
    paid_amount: Decimal
    balance_amount: Decimal
    """What is still owed on it, so the form can tell a credit that has
    somewhere to go from one that has not."""

    refundable: Decimal

    @property
    def has_party(self) -> bool:
        """Whether this document belongs to an account.

        False for a walk-in sale, which has no ledger to carry credit —
        so a return on one is refunded at the counter or not at all.
        """
        return self.party_id is not None

    @property
    def returnable_lines(self) -> tuple[ReturnableLine, ...]:
        return tuple(line for line in self.lines if line.is_returnable)


@dataclass(frozen=True, slots=True)
class ReturnableDocumentQuery:
    """Which document a return is being recorded against.

    Two ways in, because there are two: the row action on a document list
    already holds the id, and the stock register only has the number the
    customer is holding.
    """

    document_id: int | None = None
    reference: str = ""

    def __post_init__(self) -> None:
        if self.document_id is None and not self.reference.strip():
            raise ValueError("a document id or a reference is required")

    @property
    def wanted(self) -> str:
        """What was asked for, for an error message to name."""
        return self.reference.strip() or f"id={self.document_id}"
