"""
The reports, and the arithmetic that makes them mean something.

Same shape as the ledger next door: the sums live in pure functions with
no database in sight, and the use cases below them only fetch and hand
over. Everything a report *claims* is in the functions, so that is what
the tests point at.

One rule runs through all of it: **a cost that was never recorded is not a
cost of zero.** A sale line whose item had never been bought has no
margin, not a margin of a hundred per cent, and every figure here either
excludes such a line or counts it out loud.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.auth.session import CurrentUserSession
from app.application.dto.queries import (
    Ageing,
    AgeingBand,
    AgeingLine,
    AgeingQuery,
    CategorySpend,
    ItemMargin,
    ItemProfitability,
    ProfitAndLoss,
    ReportQuery,
)
from app.application.reporting.ports import OutstandingSource
from app.application.use_cases.authorized_base import AuthorizedUnitOfWorkUseCase
from app.domain.repositories.aggregates import (
    CategorySpendRow,
    CostTotals,
    ItemMarginRow,
    OutstandingRow,
    RevenueTotals,
)
from app.domain.uow import UnitOfWork

ZERO = Decimal("0.00")

UNCATEGORISED = "Uncategorised"
"""What spending with no category filed against it is called. The reports
screen has always shown this; it is named here now so the screen and the
printed page cannot word it differently."""

UNNAMED_ITEM = "Deleted item"
"""An item sold and since removed from the catalogue. The sale is still a
fact, so it still appears."""

UNNAMED_PARTY = "No party"
"""A walk-in sale or a counter purchase, on an ageing list."""

_CATEGORY_LIMIT = 500
"""Categories are a short hand-kept list; a ceiling, not a page size."""


# ---------------------------------------------------------------- profit & loss


def build_profit_and_loss(
    start: datetime,
    end: datetime,
    revenue: RevenueTotals,
    cost: CostTotals,
    spending: Iterable[CategorySpendRow],
    category_names: Mapping[int, str],
    stock_bought: Decimal,
) -> ProfitAndLoss:
    """Revenue, less what the stock cost, less what the shop cost to run.

    Purchases are not subtracted. Stock bought and not yet sold is still
    the shop's money, sitting on a shelf rather than spent — which is the
    difference between a profit and loss and the money-in-money-out figure
    this replaces.
    """
    rows = tuple(spending)
    expenses_total = sum((row.total for row in rows), ZERO)

    breakdown = tuple(
        sorted(
            (
                CategorySpend(
                    name=category_names.get(row.category_id, UNCATEGORISED)
                    if row.category_id is not None
                    else UNCATEGORISED,
                    count=row.count,
                    total=row.total,
                    share=_share(row.total, expenses_total),
                )
                for row in rows
            ),
            key=lambda line: line.total,
            reverse=True,
        )
    )

    return ProfitAndLoss(
        start=start,
        end=end,
        invoice_count=revenue.invoice_count,
        gross_revenue=revenue.gross,
        invoice_discounts=revenue.discounts,
        revenue=revenue.net,
        cost_of_goods_sold=cost.cost_of_goods_sold,
        expenses_total=expenses_total,
        expense_count=sum(row.count for row in rows),
        spending=breakdown,
        uncosted_lines=cost.uncosted_lines,
        uncosted_revenue=cost.uncosted_revenue,
        stock_bought=stock_bought,
    )


# ---------------------------------------------------------------- by item


def build_item_profitability(
    start: datetime,
    end: datetime,
    rows: Iterable[ItemMarginRow],
    item_names: Mapping[int, str],
) -> ItemProfitability:
    """What each item earned, best earner first.

    An item whose every sale was uncosted reports no cost and no margin
    rather than a total one. An item costed in part reports the part that
    is known, and says how many lines it is missing.
    """
    lines = tuple(
        sorted(
            (
                ItemMargin(
                    item_id=row.item_id,
                    name=item_names.get(row.item_id, UNNAMED_ITEM),
                    quantity_sold=row.quantity_sold,
                    revenue=row.revenue,
                    cost=_known_cost(row),
                    uncosted_lines=row.uncosted_lines,
                )
                for row in rows
            ),
            key=lambda line: line.revenue,
            reverse=True,
        )
    )

    return ItemProfitability(
        start=start,
        end=end,
        rows=lines,
        revenue=sum((line.revenue for line in lines), ZERO),
        # The known part only — the unknown part is reported as a count,
        # never folded in as if it had been free.
        cost=sum((line.cost for line in lines if line.cost is not None), ZERO),
        uncosted_lines=sum(line.uncosted_lines for line in lines),
    )


# ---------------------------------------------------------------- ageing


AGE_BANDS: tuple[tuple[str, int | None], ...] = (
    ("0-30 days", 30),
    ("31-60 days", 60),
    ("61-90 days", 90),
    ("Over 90 days", None),
)
"""How old, in bands, with the last one open-ended.

Age of the document, not lateness. There is no due date and no payment
terms anywhere in this app, so "current" and "overdue" are claims it
cannot make. If terms are added later, only the date this measures from
changes.
"""


def build_ageing(
    as_at: datetime,
    documents: Iterable[OutstandingRow],
    bands: Sequence[tuple[str, int | None]] = AGE_BANDS,
) -> Ageing:
    """Sort what is unpaid by how long it has been unpaid.

    Banded here rather than in SQL: the boundaries are the only thing in
    this report that can be wrong, and this way they are testable without
    a database.
    """
    lines: list[AgeingLine] = []
    for document in documents:
        age = max((as_at - document.occurred_at).days, 0)
        lines.append(
            AgeingLine(
                party=document.party_name or UNNAMED_PARTY,
                reference=document.reference,
                occurred_at=document.occurred_at,
                age_days=age,
                band=_band_for(age, bands),
                outstanding=document.outstanding,
            )
        )

    # Oldest first: the top of this list is what needs chasing.
    lines.sort(key=lambda line: line.age_days, reverse=True)
    total = sum((line.outstanding for line in lines), ZERO)

    # Every band, always — including the empty ones, so the strip along
    # the top of the screen keeps its shape whatever is outstanding.
    counts = {label: 0 for label, _ in bands}
    totals = {label: ZERO for label, _ in bands}
    for line in lines:
        counts[line.band] += 1
        totals[line.band] += line.outstanding

    return Ageing(
        as_at=as_at,
        bands=tuple(
            AgeingBand(
                label=label,
                count=counts[label],
                total=totals[label],
                share=_share(totals[label], total),
            )
            for label, _ in bands
        ),
        lines=tuple(lines),
        total=total,
    )


def _known_cost(row: ItemMarginRow) -> Decimal | None:
    """What this item's sales cost, or None if that is simply not known.

    A zero from the query means every line of it was uncosted — the sum
    had nothing to add. Reported as None so the screen shows a dash, not a
    hundred per cent margin. A partly costed item keeps the part that is
    known and carries its `uncosted_lines` count alongside.
    """
    if row.uncosted_lines and row.cost == ZERO:
        return None
    return row.cost


def _band_for(age_days: int, bands: Sequence[tuple[str, int | None]]) -> str:
    for label, upper in bands:
        if upper is None or age_days <= upper:
            return label
    return bands[-1][0]


def _share(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return ZERO
    return (part * Decimal(100) / whole).quantize(Decimal("0.1"))


# ---------------------------------------------------------------- use cases


class GetProfitAndLossUseCase(AuthorizedUnitOfWorkUseCase[ReportQuery, ProfitAndLoss]):
    """A period's trading, as an income statement."""

    def execute(self, request: ReportQuery) -> ProfitAndLoss:
        self.require_permission(Permission.VIEW_REPORTS)

        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            purchases = self.require(uow.purchases, "purchases")
            expenses = self.require(uow.expenses, "expenses")
            categories = self.require(uow.expense_categories, "expense_categories")

            return build_profit_and_loss(
                request.start,
                request.end,
                sales.revenue_between(request.start, request.end),
                sales.cost_of_sales_between(request.start, request.end),
                expenses.total_by_category_between(request.start, request.end),
                {
                    category.id: category.name
                    for category in categories.list(limit=_CATEGORY_LIMIT)
                    if category.id is not None
                },
                purchases.spend_between(request.start, request.end),
            )


class GetItemProfitabilityUseCase(AuthorizedUnitOfWorkUseCase[ReportQuery, ItemProfitability]):
    """Which items earned the money, and which only moved it."""

    def execute(self, request: ReportQuery) -> ItemProfitability:
        self.require_permission(Permission.VIEW_REPORTS)

        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            items = self.require(uow.inventory_items, "inventory_items")

            rows = sales.margin_by_item_between(request.start, request.end)
            return build_item_profitability(
                request.start,
                request.end,
                rows,
                items.names_by_id({row.item_id for row in rows}),
            )


class GetAgeingUseCase(AuthorizedUnitOfWorkUseCase[AgeingQuery, Ageing]):
    """How long money has been outstanding.

    One use case, assembled two ways — receivables and payables are the
    same question asked of different documents, exactly as the two ledgers
    are. See `app.application.reporting.sources`.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
        *,
        source: OutstandingSource,
    ) -> None:
        super().__init__(uow, current_user_session, authorization_service)
        self.source = source

    def execute(self, request: AgeingQuery) -> Ageing:
        self.require_permission(Permission.VIEW_REPORTS)

        with self.uow as uow:
            return build_ageing(request.as_at, self.source.documents(uow, request.as_at))
