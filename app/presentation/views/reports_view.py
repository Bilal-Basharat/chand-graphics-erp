"""
Reports screen: money in, money out, and what is still unpaid, for a period.

There is no reporting use case in the backend — this composes the existing
date-range queries (sales, purchases, expenses) and reduces them here. The
volume a single print shop produces in a month makes that entirely
reasonable; if it ever isn't, the aggregation belongs in a use case, not
in a smarter widget.

Deliberately not a `CollectionView`: this screen is several panels of
summary, not one list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.container import AppContainer
from app.presentation.formatting import TO_COLLECT, TO_PAY, counted, date_only, money
from app.presentation.viewmodels.base import BaseViewModel
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.page_header import PageHeader
from app.presentation.widgets.page_scroll import page_scroll
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.stat_tile import StatTile
from app.presentation.widgets.table_model import Column

_ZERO = Decimal("0.00")


@dataclass(slots=True)
class CategoryRow:
    name: str
    count: int
    total: Decimal


@dataclass(slots=True)
class ReportSummary:
    """Everything the screen renders, computed once off the UI thread."""

    start: object
    end: object
    sales_total: Decimal = _ZERO
    sales_count: int = 0
    receivable: Decimal = _ZERO
    purchases_total: Decimal = _ZERO
    purchases_count: int = 0
    payable: Decimal = _ZERO
    expenses_total: Decimal = _ZERO
    expenses_count: int = 0
    expense_breakdown: list[CategoryRow] = field(default_factory=list)

    @property
    def gross_profit(self) -> Decimal:
        """Sales less what was bought and spent in the same window.

        A period measure, not true cost-of-goods-sold: stock bought this
        month may be sold next. Labelled "net movement" on screen so it
        isn't mistaken for margin.
        """
        return self.sales_total - self.purchases_total - self.expenses_total


class ReportsViewModel(BaseViewModel):
    summaryLoaded = Signal(object)  # ReportSummary

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period

    def load(self) -> None:
        self.run_async(self._build_summary, on_success=self.summaryLoaded.emit)

    def _build_summary(self) -> ReportSummary:
        query = self._period.as_query(limit=2000)
        start, end = self._period.range()

        sales = self._container.list_sales_by_date_range_use_case().execute(query)
        purchases = self._container.list_purchases_by_date_range_use_case().execute(query)
        expenses = self._container.list_expenses_by_date_range_use_case().execute(query)
        categories = self._container.list_expense_categories_use_case().execute(500)

        category_names = {c.id: c.name for c in categories}
        grouped: dict[str, CategoryRow] = {}
        for expense in expenses:
            name = category_names.get(expense.category_id, "Uncategorised")
            row = grouped.get(name)
            if row is None:
                grouped[name] = CategoryRow(name=name, count=1, total=expense.total_amount)
            else:
                row.count += 1
                row.total += expense.total_amount

        return ReportSummary(
            start=start,
            end=end,
            sales_total=sum((s.grand_total for s in sales), _ZERO),
            sales_count=len(sales),
            receivable=sum((s.balance_amount for s in sales), _ZERO),
            purchases_total=sum((p.grand_total for p in purchases), _ZERO),
            purchases_count=len(purchases),
            payable=sum((p.balance_amount for p in purchases), _ZERO),
            expenses_total=sum((e.total_amount for e in expenses), _ZERO),
            expenses_count=len(expenses),
            expense_breakdown=sorted(grouped.values(), key=lambda r: r.total, reverse=True),
        )


class ReportsView(QWidget):
    def __init__(
        self,
        view_model: ReportsViewModel,
        period: PeriodSelection,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._period = period
        # Denominator for the share column; set when a summary lands.
        self._expenses_total = _ZERO

        # Six tiles over two rows plus a table — taller than a 768px
        # laptop screen, so it scrolls.
        outer = QVBoxLayout(page_scroll(self))
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        header = PageHeader(
            ("Finance", "Reports"),
            "Reports",
            "Money in, money out, and what is still unpaid over a period.",
        )
        selector = PeriodSelector(period)
        selector.periodChanged.connect(self.reload)
        header.add_widget(selector)
        outer.addWidget(header)

        self._range_label = QLabel("")
        self._range_label.setProperty("role", "pageSub")
        outer.addWidget(self._range_label)

        outer.addLayout(self._build_tiles())
        outer.addWidget(self._build_breakdown_panel(), 1)

        view_model.summaryLoaded.connect(self._on_summary)
        view_model.errorOccurred.connect(self._on_error)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self.reload()

    def reload(self) -> None:
        self._view_model.load()

    # ---------------- construction ----------------

    def _build_tiles(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(14)

        self._tiles = {
            "sales": StatTile("Sales", money(_ZERO), "0 invoices"),
            "purchases": StatTile("Purchases", money(_ZERO), "0 purchases"),
            "expenses": StatTile("Expenses", money(_ZERO), "0 expenses"),
            "net": StatTile("Net movement", money(_ZERO), "Sales less purchases and expenses"),
            "receivable": StatTile(TO_COLLECT, money(_ZERO), "Unpaid on sales"),
            "payable": StatTile(TO_PAY, money(_ZERO), "Unpaid on purchases"),
        }
        for index, tile in enumerate(self._tiles.values()):
            grid.addWidget(tile, index // 3, index % 3)
            grid.setColumnStretch(index % 3, 1)
        return grid

    def _build_breakdown_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(1, 0, 1, 1)
        layout.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(18, 14, 18, 10)
        title = QLabel("Spending by category")
        title.setProperty("role", "panelTitle")
        self._breakdown_note = QLabel("")
        self._breakdown_note.setProperty("role", "panelSub")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self._breakdown_note)
        layout.addLayout(title_row)

        self._breakdown = DataTable(
            [
                Column("CATEGORY", lambda r: r.name),
                Column("ENTRIES", lambda r: r.count, align="right", width=110),
                Column("TOTAL", lambda r: money(r.total), align="right", width=160),
                Column("SHARE", self._share, align="right", width=110),
            ],
            placeholder="No expenses recorded in this period.",
        )
        layout.addWidget(self._breakdown, 1)
        return panel

    def _share(self, row: CategoryRow) -> str:
        if not self._expenses_total:
            return "—"
        return f"{row.total / self._expenses_total * 100:.1f}%"

    # ---------------- state ----------------

    def _on_summary(self, summary: ReportSummary) -> None:
        self._expenses_total = summary.expenses_total
        self._range_label.setText(
            f"{self._period.label} — {date_only(summary.start)} to {date_only(summary.end)}"
        )

        self._tiles["sales"].set_value(money(summary.sales_total))
        self._tiles["sales"].set_note(counted(summary.sales_count, "invoice"))
        self._tiles["purchases"].set_value(money(summary.purchases_total))
        self._tiles["purchases"].set_note(counted(summary.purchases_count, "purchase"))
        self._tiles["expenses"].set_value(money(summary.expenses_total))
        self._tiles["expenses"].set_note(counted(summary.expenses_count, "expense"))
        self._tiles["net"].set_value(money(summary.gross_profit))
        self._tiles["receivable"].set_value(money(summary.receivable))
        self._tiles["payable"].set_value(money(summary.payable))

        self._breakdown.set_rows(summary.expense_breakdown)
        self._breakdown_note.setText(
            counted(len(summary.expense_breakdown), "category", "categories")
        )

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Reports", message)
