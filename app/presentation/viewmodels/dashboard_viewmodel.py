"""
Dashboard aggregation. There is no dedicated backend summary use case yet
(flagged in the implementation plan), so this reduces this month's sales
and purchases client-side. Fine at this data volume (a small print shop's
monthly document count); would move server-side first if that changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from PySide6.QtCore import Signal

from app.application.dto.commands import DateRangeQuery
from app.application.dto.queries import SearchQuery
from app.container import AppContainer
from app.presentation.viewmodels.base import BaseViewModel


@dataclass(slots=True)
class DocumentRow:
    document_no: str
    doc_type: str  # "Sale" | "Purchase"
    party: str
    date: datetime
    total: Decimal
    balance: Decimal
    status: str  # "Paid" | "Partial" | "Unpaid"


@dataclass(slots=True)
class ActivityRow:
    title: str
    meta: str
    when: datetime


@dataclass(slots=True)
class MonthTotals:
    """One column of the sales-versus-purchases chart."""

    label: str
    sales: Decimal
    purchases: Decimal


@dataclass(slots=True)
class DashboardData:
    sales_total: Decimal
    sales_count: int
    purchases_total: Decimal
    purchases_count: int
    low_stock_count: int
    pending_balance: Decimal
    pending_parties: int
    recent_documents: list[DocumentRow]
    recent_activity: list[ActivityRow]
    monthly: list[MonthTotals]


_CHART_MONTHS = 12
"""How many months the chart covers, and therefore how far back documents
are fetched.

One fetch feeds all of it: the tiles take this month's slice, the lists
take the newest few, and the chart buckets the lot. A second query for the
chart alone would read the same rows twice. At a print shop's volume the
reduction stays client-side, as the rest of this module already does — if
that volume ever changes, an aggregate query is the thing to add first.
"""
_DOCUMENT_LIMIT = 2000

_RECENT_DOCUMENTS = 6
_RECENT_ACTIVITY = 20


def _status_for(balance: Decimal, total: Decimal) -> str:
    if balance <= 0:
        return "Paid"
    if balance >= total:
        return "Unpaid"
    return "Partial"


class DashboardViewModel(BaseViewModel):
    dashboardLoaded = Signal(object)  # DashboardData

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container

    def load(self) -> None:
        self.run_async(self._load_sync, on_success=self.dashboardLoaded.emit)

    def _load_sync(self) -> DashboardData:
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        months = _recent_months(month_start, _CHART_MONTHS)
        date_range = DateRangeQuery(start=months[0], end=now, limit=_DOCUMENT_LIMIT)

        sales = self._container.list_sales_by_date_range_use_case().execute(date_range)
        purchases = self._container.list_purchases_by_date_range_use_case().execute(date_range)
        low_stock_cards = self._container.list_low_stock_cards_use_case().execute(500)
        low_stock_items = self._container.list_low_stock_inventory_items_use_case().execute(500)

        # Name lookups for the document rows below — an empty term lists all.
        all_parties = SearchQuery(term="", limit=1000)
        customers = {c.id: c.name for c in self._container.search_customers_use_case().execute(all_parties)}
        suppliers = {s.id: s.name for s in self._container.search_suppliers_use_case().execute(all_parties)}

        # The tiles are a monthly figure; the lists below are "latest".
        month_sales = [s for s in sales if s.created_at and s.created_at >= month_start]
        month_purchases = [p for p in purchases if p.created_at and p.created_at >= month_start]

        pending_parties: set[tuple[str, int]] = set()
        pending_balance = Decimal("0.00")
        documents: list[DocumentRow] = []
        activity: list[ActivityRow] = []

        for sale in sales:
            party = customers.get(sale.customer_id, "Walk-in customer") if sale.customer_id else "Walk-in customer"
            documents.append(
                DocumentRow(
                    document_no=sale.invoice_no,
                    doc_type="Sale",
                    party=party,
                    date=sale.created_at,
                    total=sale.grand_total,
                    balance=sale.balance_amount,
                    status=_status_for(sale.balance_amount, sale.grand_total),
                )
            )
            activity.append(
                ActivityRow(
                    title=f"Invoice {sale.invoice_no} created",
                    meta=f"{party} • PKR {sale.grand_total:,.0f}",
                    when=sale.created_at,
                )
            )
            activity.extend(
                _payment_activity(
                    sale.payments,
                    lambda payment: payment.received_at,
                    title=f"Payment received on {sale.invoice_no}",
                    party=party,
                )
            )

        for purchase in purchases:
            party = suppliers.get(purchase.supplier_id, "Unknown supplier") if purchase.supplier_id else "Unknown supplier"
            documents.append(
                DocumentRow(
                    document_no=purchase.purchase_no,
                    doc_type="Purchase",
                    party=party,
                    date=purchase.created_at,
                    total=purchase.grand_total,
                    balance=purchase.balance_amount,
                    status=_status_for(purchase.balance_amount, purchase.grand_total),
                )
            )
            activity.append(
                ActivityRow(
                    title=f"Purchase {purchase.purchase_no} recorded",
                    meta=f"{party} • PKR {purchase.grand_total:,.0f}",
                    when=purchase.created_at,
                )
            )
            activity.extend(
                _payment_activity(
                    purchase.payments,
                    lambda payment: payment.paid_at,
                    title=f"Payment made on {purchase.purchase_no}",
                    party=party,
                )
            )

        for document, kind, party_id in [
            *((s, "customer", s.customer_id) for s in month_sales),
            *((p, "supplier", p.supplier_id) for p in month_purchases),
        ]:
            if document.balance_amount > 0:
                pending_balance += document.balance_amount
                pending_parties.add((kind, party_id or 0))

        documents.sort(key=lambda d: d.date or datetime.min, reverse=True)
        activity.sort(key=lambda a: a.when or datetime.min, reverse=True)

        return DashboardData(
            sales_total=sum((s.grand_total for s in month_sales), Decimal("0.00")),
            sales_count=len(month_sales),
            purchases_total=sum((p.grand_total for p in month_purchases), Decimal("0.00")),
            purchases_count=len(month_purchases),
            low_stock_count=len(low_stock_cards) + len(low_stock_items),
            pending_balance=pending_balance,
            pending_parties=len(pending_parties),
            recent_documents=documents[:_RECENT_DOCUMENTS],
            recent_activity=activity[:_RECENT_ACTIVITY],
            monthly=_monthly_totals(months, sales, purchases),
        )


def _recent_months(month_start: datetime, count: int) -> list[datetime]:
    """The first day of each of the last `count` months, oldest first."""
    months = [month_start]
    for _ in range(count - 1):
        # Stepping back a day from the first lands in the previous month
        # whatever its length, which is why this isn't arithmetic on 30.
        months.append((months[-1] - timedelta(days=1)).replace(day=1))
    return list(reversed(months))


def _monthly_totals(months: list[datetime], sales: list, purchases: list) -> list[MonthTotals]:
    """Sales and purchases bucketed by the month they were recorded in.

    Every month in the range gets a column, including the empty ones: a
    chart that silently drops quiet months draws a busy year.
    """
    keys = [(month.year, month.month) for month in months]
    sales_by_month = {key: Decimal("0.00") for key in keys}
    purchases_by_month = dict(sales_by_month)

    for document, bucket in (
        *((sale, sales_by_month) for sale in sales),
        *((purchase, purchases_by_month) for purchase in purchases),
    ):
        when = document.created_at
        if when is None:
            continue
        key = (when.year, when.month)
        if key in bucket:
            bucket[key] += document.grand_total

    return [
        MonthTotals(
            label=f"{month:%b}",
            sales=sales_by_month[key],
            purchases=purchases_by_month[key],
        )
        for month, key in zip(months, keys)
    ]


def _payment_activity(payments, dated, *, title: str, party: str) -> list[ActivityRow]:
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
                meta=f"{party} • PKR {payment.amount:,.0f}",
                when=when,
            )
        )
    return rows
