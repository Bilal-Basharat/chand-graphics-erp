"""
Dashboard aggregation. There is no dedicated backend summary use case yet
(flagged in the implementation plan), so this reduces the period's sales
and purchases client-side. Fine at this data volume (a small print shop's
document count); would move server-side first if that changes.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from tkinter.font import names

from PySide6.QtCore import Signal

from app.application.dto.commands import DateRangeQuery
from app.application.dto.queries import SearchQuery
from app.container import AppContainer
from app.presentation.formatting import payment_method_name, pkr
from app.presentation.navigation.routes import Route
from app.presentation.records.card import RecordCard
from app.presentation.viewmodels.document_items import ItemCatalogue, payment_lines
from app.presentation.viewmodels.document_items import payment_lines
from app.presentation.records.builders import job_card, purchase_card, sale_card
from app.presentation.viewmodels.base import BaseViewModel
from app.presentation.viewmodels.document_items import ItemCatalogue, payment_lines
from app.presentation.viewmodels.job_items import JobCatalogue
from app.presentation.widgets.period_selector import PeriodSelection


@dataclass(slots=True)
class DocumentRow:
    document_no: str
    doc_type: str  # "Sale" | "Job" | "Purchase"
    party: str
    date: datetime
    total: Decimal
    balance: Decimal
    status: str  # "Paid" | "Partial" | "Unpaid" | "Cancelled"
    route: Route
    card: RecordCard
    """The screen this document lives on, and the document itself written
    out. Both are settled here, where the record and every name it refers
    to are already in hand — the dashboard's own panels hold display rows,
    not entities, and re-fetching one to open it would be a second answer
    to a question already answered."""

@dataclass(slots=True)
class ActivityRow:
    title: str
    meta: str
    when: datetime
    card: RecordCard
    """The record this entry is about, written out. Every entry against
    one document — raised, completed, paid — carries the same card: they
    are moments in the life of one record, not records of their own."""


@dataclass(slots=True)
class BucketTotals:
    """One column of the money chart."""

    label: str
    sales: Decimal
    jobs: Decimal
    purchases: Decimal
    expenses: Decimal


@dataclass(slots=True)
class DashboardData:
    period_label: str
    sales_total: Decimal
    sales_count: int
    purchases_total: Decimal
    purchases_count: int
    low_stock_count: int
    receivable: Decimal
    payable: Decimal
    """Still unpaid on this period's sales, and on its purchases. Kept
    apart rather than netted here: the screen decides how to say it, and
    both halves are worth showing behind the one figure it settles on."""
    recent_documents: list[DocumentRow]
    recent_activity: list[ActivityRow]
    buckets: list[BucketTotals]


_DOCUMENT_LIMIT = 2000
"""One fetch feeds the whole screen: the tiles total it, the lists take
the newest few, and the chart buckets the lot. A second query for the
chart alone would read the same rows twice. At a print shop's volume the
reduction stays client-side, as the rest of this module already does — if
that volume ever changes, an aggregate query is the thing to add first.
"""

_RECENT_DOCUMENTS = 6
_RECENT_ACTIVITY = 20

_CATALOGUE_LIMIT = 500
"""How much master data a card can name. The same figure every screen
that loads these catalogues uses."""


@dataclass(slots=True)
class _Catalogues:
    """The three lookups a written-out document needs, fetched together."""

    products: ItemCatalogue
    jobs: JobCatalogue
    method_name: Callable[[int | None], str]


_CATALOGUE_LIMIT = 500
"""How much master data a card can name. The same figure every screen
that loads these catalogues uses."""


@dataclass(slots=True)
class _Catalogues:
    """The three lookups a written-out document needs, fetched together."""

    products: ItemCatalogue
    method_name: Callable[[int | None], str]


def _status_for(balance: Decimal, total: Decimal) -> str:
    if balance <= 0:
        return "Paid"
    if balance >= total:
        return "Unpaid"
    return "Partial"


class DashboardViewModel(BaseViewModel):
    dashboardLoaded = Signal(object)  # DashboardData

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period

    def load(self) -> None:
        self.run_async(self._load_sync, on_success=self.dashboardLoaded.emit)

    def _catalogues(self) -> _Catalogues:
        """Names for everything the cards below refer to.

        The dashboard writes out every document it lists, so it needs the
        same catalogues the document screens hold. They are small
        master-data tables next to the documents already fetched above,
        and reading them once here is what lets a card open from the
        dashboard without going back to the database for it.
        """
        products = ItemCatalogue()
        products.set_products(
            self._container.list_cards_use_case().execute(_CATALOGUE_LIMIT),
            self._container.list_inventory_items_use_case().execute(_CATALOGUE_LIMIT),
        )
        job_catalogue = JobCatalogue()
        job_catalogue.set_reference(
            product_types=self._container.list_product_types_use_case().execute(_CATALOGUE_LIMIT),
            labour_charge_types=self._container.list_labour_charge_types_use_case().execute(
                _CATALOGUE_LIMIT
            ),
            cards=self._container.list_cards_use_case().execute(_CATALOGUE_LIMIT),
            inventory_items=self._container.list_inventory_items_use_case().execute(
                _CATALOGUE_LIMIT
            ),
        )
        methods = {
            m.id: m.name for m in self._container.list_payment_methods_use_case().execute(100)
        }
        return _Catalogues(
            products=products,
            jobs=job_catalogue,
            method_name=lambda method_id: payment_method_name(methods.get(method_id)),
        )

    def _load_sync(self) -> DashboardData:
        start, end = self._period.range()
        date_range = DateRangeQuery(start=start, end=end, limit=_DOCUMENT_LIMIT)

        sales = self._container.list_sales_by_date_range_use_case().execute(date_range)
        jobs = self._container.list_jobs_by_date_range_use_case().execute(date_range)
        purchases = self._container.list_purchases_by_date_range_use_case().execute(date_range)
        expenses = self._container.list_expenses_by_date_range_use_case().execute(date_range)
        low_stock_cards = self._container.list_low_stock_cards_use_case().execute(500)
        low_stock_items = self._container.list_low_stock_inventory_items_use_case().execute(500)

        # Name lookups for the document rows below — an empty term lists all.
        all_parties = SearchQuery(term="", limit=1000)
        customers = {c.id: c.name for c in self._container.search_customers_use_case().execute(all_parties)}
        suppliers = {s.id: s.name for s in self._container.search_suppliers_use_case().execute(all_parties)}
        names = self._catalogues()
        documents: list[DocumentRow] = []
        activity: list[ActivityRow] = []

        for sale in sales:
            party = customers.get(sale.customer_id, "Walk-in customer") if sale.customer_id else "Walk-in customer"
            card = sale_card(
                sale,
                customer=party,
                items=names.products.lines_of(sale),
                payments=payment_lines(
                    sale,
                    dated=lambda payment: payment.received_at or payment.created_at,
                    method_name=names.method_name,
                ),
            )
            documents.append(
                DocumentRow(
                    document_no=sale.invoice_no,
                    doc_type="Sale",
                    party=party,
                    date=sale.created_at,
                    total=sale.grand_total,
                    balance=sale.balance_amount,
                    status=_status_for(sale.balance_amount, sale.grand_total),
                    route=Route.SALES,
                    card=card,
                )
            )
            activity.append(
                ActivityRow(
                    title=f"Invoice {sale.invoice_no} created",
                    meta=f"{party} • {pkr(sale.grand_total)}",
                    when=sale.created_at,
                    card=card,
                )
            )
            activity.extend(
                _payment_activity(
                    sale.payments,
                    lambda payment: payment.received_at,
                    title=f"Payment received on {sale.invoice_no}",
                    party=party,
                    card=card,
                )
            )

        for job in jobs:
            party = customers.get(job.customer_id, "Walk-in customer") if job.customer_id else "Walk-in customer"
            card = job_card(
                job,
                customer=party,
                items=names.jobs.lines_of(job),
                payments=payment_lines(
                    job,
                    dated=lambda payment: payment.created_at,
                    method_name=names.method_name,
                ),
            )
            documents.append(
                DocumentRow(
                    document_no=job.job_no,
                    doc_type="Job",
                    party=party,
                    date=job.created_at,
                    total=job.grand_total,
                    balance=job.balance_amount,
                    # A cancelled job owes nothing, which `_status_for`
                    # would read as settled. It was not settled; it was
                    # called off, and the row should say so.
                    status="Cancelled"
                    if job.is_void
                    else _status_for(job.balance_amount, job.grand_total),
                    route=Route.JOBS,
                    card=card,
                )
            )
            activity.extend(_job_activity(job, party, card))
            activity.extend(
                _payment_activity(
                    # A cancelled job's refunds are payments too, and
                    # showing them as money received would be a lie about
                    # which way it went.
                    [p for p in job.payments if not p.is_refund],
                    lambda payment: payment.created_at,
                    title=f"Payment received on {job.job_no}",
                    party=party,
                    card=card,
                )
            )

        for purchase in purchases:
            party = suppliers.get(purchase.supplier_id, "Unknown supplier") if purchase.supplier_id else "Unknown supplier"
            card = purchase_card(
                purchase,
                supplier=party,
                items=names.products.lines_of(purchase),
                payments=payment_lines(
                    purchase,
                    dated=lambda payment: payment.paid_at or payment.created_at,
                    method_name=names.method_name,
                ),
            )
            documents.append(
                DocumentRow(
                    document_no=purchase.purchase_no,
                    doc_type="Purchase",
                    party=party,
                    date=purchase.created_at,
                    total=purchase.grand_total,
                    balance=purchase.balance_amount,
                    status=_status_for(purchase.balance_amount, purchase.grand_total),
                    route=Route.PURCHASES,
                    card=card,
                )
            )
            activity.append(
                ActivityRow(
                    title=f"Purchase {purchase.purchase_no} recorded",
                    meta=f"{party} • {pkr(purchase.grand_total)}",
                    when=purchase.created_at,
                    card=card,
                )
            )
            activity.extend(
                _payment_activity(
                    purchase.payments,
                    lambda payment: payment.paid_at,
                    title=f"Payment made on {purchase.purchase_no}",
                    party=party,
                    card=card,
                )
            )


        # Overpayments are ignored rather than netted off: a document paid
        # more than its total is a recording mistake, not money owed the
        # other way, and letting it reduce the figure would hide it.
        #
        # Jobs count towards what is owed alongside sales — a customer who
        # has not paid for their bill books owes exactly as much as one who
        # has not paid for their cards, and the documents panel below lists
        # both. A cancelled job's balance is already zero.
        receivable = sum(
            (d.balance_amount for d in (*sales, *jobs) if d.balance_amount > 0),
            Decimal("0.00"),
        )
        payable = sum((p.balance_amount for p in purchases if p.balance_amount > 0), Decimal("0.00"))

        documents.sort(key=lambda d: d.date or datetime.min, reverse=True)
        activity.sort(key=lambda a: a.when or datetime.min, reverse=True)

        return DashboardData(
            period_label=self._period.label,
            sales_total=sum((s.grand_total for s in sales), Decimal("0.00")),
            sales_count=len(sales),
            purchases_total=sum((p.grand_total for p in purchases), Decimal("0.00")),
            purchases_count=len(purchases),
            low_stock_count=len(low_stock_cards) + len(low_stock_items),
            receivable=receivable,
            payable=payable,
            recent_documents=documents[:_RECENT_DOCUMENTS],
            recent_activity=activity[:_RECENT_ACTIVITY],
            buckets=_bucket_totals(start, end, sales, jobs, purchases, expenses),
        )


# How wide a period has to be before its columns step up a unit. A day per
# column reads well for a week or a month and turns into a picket fence
# beyond that; a year per column is only worth it once months would run
# off the axis.
_DAILY_UP_TO = timedelta(days=62)
_MONTHLY_UP_TO = timedelta(days=1100)  # about three years


def _day_starts(begin: datetime, end: datetime) -> list[datetime]:
    days = []
    day = begin.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        days.append(day)
        day += timedelta(days=1)
    return days


def _month_starts(begin: datetime, end: datetime) -> list[datetime]:
    months = []
    month = begin.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while month <= end:
        months.append(month)
        # Stepping past the longest month and snapping back to the 1st
        # lands in the next one whatever its length.
        month = (month + timedelta(days=32)).replace(day=1)
    return months


def _year_starts(begin: datetime, end: datetime) -> list[datetime]:
    years = []
    year = begin.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    while year <= end:
        years.append(year)
        year = year.replace(year=year.year + 1)
    return years


def _bucket_totals(
    start: datetime,
    end: datetime,
    sales: list,
    jobs: list,
    purchases: list,
    expenses: list,
) -> list[BucketTotals]:
    """Money in and out, bucketed across the period, oldest first.

    Every bucket in the range gets a column, including the empty ones: a
    chart that silently drops quiet stretches draws a busy period.

    The columns start at the first record rather than at the period's own
    start, because "All time" begins at an epoch no shop traded in and
    would otherwise draw decades of nothing before the first sale.
    """
    dated = [d.created_at for d in (*sales, *jobs, *purchases, *expenses) if d.created_at]
    begin = max(start, min(dated)) if dated else start

    span = end - begin
    if span <= _DAILY_UP_TO:
        starts = _day_starts(begin, end)
        key: Callable[[datetime], object] = lambda when: (when.year, when.month, when.day)
        label: Callable[[datetime], str] = lambda at: f"{at:%d %b}"
    elif span <= _MONTHLY_UP_TO:
        starts = _month_starts(begin, end)
        key = lambda when: (when.year, when.month)
        # The year is only worth the width when the period crosses one.
        pattern = "%b" if begin.year == end.year else "%b %y"
        label = lambda at: format(at, pattern)
    else:
        starts = _year_starts(begin, end)
        key = lambda when: when.year
        label = lambda at: f"{at:%Y}"

    keys = [key(at) for at in starts]
    sold = {bucket: Decimal("0.00") for bucket in keys}
    made = dict(sold)
    bought = dict(sold)
    spent = dict(sold)

    # An expense totals under a different name from a document, which is
    # why each source brings its own amount rather than sharing one field.
    for records, totals, amount_of in (
        (sales, sold, lambda record: record.grand_total),
        (jobs, made, lambda record: record.grand_total),
        (purchases, bought, lambda record: record.grand_total),
        (expenses, spent, lambda record: record.total_amount),
    ):
        for record in records:
            when = record.created_at
            if when is None:
                continue
            bucket = key(when)
            if bucket in totals:
                totals[bucket] += amount_of(record)

    return [
        BucketTotals(
            label=label(at),
            sales=sold[bucket],
            jobs=made[bucket],
            purchases=bought[bucket],
            expenses=spent[bucket],
        )
        for at, bucket in zip(starts, keys)
    ]


def _job_activity(job, party: str, card: RecordCard) -> list[ActivityRow]:
    """A job's own milestones, each dated by the stamp that records it.

    A job is not one event. It is written down, it comes off the press, it
    goes out of the door — or it is called off — and each of those is a
    thing someone scanning the feed is looking for, at its own moment. So
    each is its own entry rather than one row whose wording keeps changing
    under the same timestamp.

    The amount is what the work was quoted at, on every entry including a
    cancelled job's. That job's total reads zero from the moment it is
    called off, and "Job X recorded • PKR 0" is not what happened.
    """
    quoted = job.subtotal - job.discount_amount
    milestones = (
        ("recorded", job.created_at),
        ("completed", job.completed_at),
        ("delivered", job.delivered_at),
        ("cancelled", job.cancelled_at),
    )
    return [
        ActivityRow(
            title=f"Job {job.job_no} {word}",
            meta=f"{party} • {pkr(quoted)}",
            when=when,
            card=card,
        )
        for word, when in milestones
        if when is not None
    ]


def _payment_activity(
    payments, dated, *, title: str, party: str, card: RecordCard
) -> list[ActivityRow]:
    """Activity rows for the instalments against one document.

    Undated payments are skipped rather than dated `now`: an activity feed
    ordered by time cannot carry an entry that has no time without pushing
    something true out of the list.
    """
    rows = []
    for payment in payments:
        when = dated(payment) or payment.created_at
        if when is None:
            continue
        rows.append(
            ActivityRow(
                title=title,
                meta=f"{party} • {pkr(payment.amount)}",
                when=when,
                card=card,
            )
        )
    return rows
