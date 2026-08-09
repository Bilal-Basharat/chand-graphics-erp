"""
Dashboard screen: KPI tiles, the sales-versus-purchases chart, recent
activity and recent documents. Purely rendering — all data comes from
DashboardViewModel.

One period control at the top governs the whole page. Four panels each
carrying their own idea of "when" is how a dashboard stops being a single
answer: the tiles used to report a month, the chart a year and the lists
everything ever, so no two of them described the same trading.

Its content is a stack of panels at their natural heights rather than one
table that stretches to fit, so it sits in a page scroller — see
widgets/page_scroll.py. Without it the last panel was simply cut off by
the bottom of the window.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.presentation.dialogs.record_card_dialog import RecordCardDialog
from app.presentation.navigation.routes import Route
from app.presentation.theme import tokens as t
from app.presentation.viewmodels.dashboard_viewmodel import DashboardData, DashboardViewModel
from app.presentation.formatting import (
    SETTLED,
    TO_COLLECT_SHORT,
    TO_PAY_SHORT,
    counted,
    date_only,
    money,
    pkr,
)
from app.presentation.views.collection_view import VIEW_ACTION
from app.presentation.widgets.activity_list import ActivityList
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.page_scroll import page_scroll
from app.presentation.widgets.period_bars import PeriodBars
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.row_actions import RowActionsDelegate
from app.presentation.widgets.stat_tile import StatTile
from app.presentation.widgets.table_model import Column


def _document_status_color(row) -> str:
    """Same status colours as the purchases and payments screens, so a
    document reads the same wherever it appears."""
    if row.status == "Paid":
        return t.SUCCESS
    if row.status == "Partial":
        return t.WARNING
    return t.DANGER


class DashboardView(QWidget):
    recordRequested = Signal(Route, str)
    """A screen to open and the document number to find on it. The
    dashboard knows which record an entry is about; only the shell knows
    what a screen is, so it routes."""

    def __init__(
        self,
        view_model: DashboardViewModel,
        period: PeriodSelection,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._period = period
        self._loaded_once = False

        outer = QVBoxLayout(page_scroll(self))
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(0)

        crumb = QLabel("Home / Dashboard")
        crumb.setProperty("role", "crumb")
        outer.addWidget(crumb)
        outer.addSpacing(6)

        outer.addLayout(self._build_page_head())
        outer.addSpacing(16)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        # Low stock is deliberately not period-labelled: it is what is on
        # the shelves right now, and no choice of period changes it.
        self._sales_tile = StatTile("Sales", "PKR 0")
        self._purchases_tile = StatTile("Purchases", "PKR 0")
        self._low_stock_tile = StatTile("Low stock items", "0", "Below minimum stock level")
        self._balance_tile = StatTile("Unpaid balances", "PKR 0", SETTLED)
        for tile in (self._sales_tile, self._purchases_tile, self._low_stock_tile, self._balance_tile):
            stats_row.addWidget(tile)
        outer.addLayout(stats_row)
        outer.addSpacing(18)

        cols = QHBoxLayout()
        cols.setSpacing(16)
        cols.addWidget(self._build_chart_panel(), 4)
        cols.addWidget(self._build_activity_panel(), 3)
        outer.addLayout(cols)
        outer.addSpacing(18)

        outer.addWidget(self._build_documents_panel())
        outer.addStretch(1)

        self._view_model.dashboardLoaded.connect(self._on_loaded)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._view_model.load()

    def _build_page_head(self) -> QHBoxLayout:
        row = QHBoxLayout()
        text_col = QVBoxLayout()
        title = QLabel("Dashboard")
        title.setProperty("role", "pageTitle")
        sub = QLabel("Sales, purchases, stock and balances at a glance.")
        sub.setProperty("role", "pageSub")
        text_col.addWidget(title)
        text_col.addWidget(sub)
        row.addLayout(text_col)
        row.addStretch(1)

        # The same control, in the same place, as every list screen's
        # toolbar — it just governs four panels here instead of one table.
        selector = PeriodSelector(self._period)
        selector.periodChanged.connect(self._view_model.load)
        row.addWidget(selector)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("variant", "outline")
        refresh_btn.clicked.connect(self._view_model.load)
        row.addWidget(refresh_btn)
        return row

    def _panel_header(self, title: str, sub: str) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setContentsMargins(18, 14, 18, 10)
        wrap.setSpacing(2)
        title_label = QLabel(title)
        title_label.setProperty("role", "panelTitle")
        sub_label = QLabel(sub)
        sub_label.setProperty("role", "panelSub")
        wrap.addWidget(title_label)
        wrap.addWidget(sub_label)
        return wrap

    def _build_chart_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(
            self._panel_header(
                "Money in and out", "Sales, purchases and expenses — PKR"
            )
        )

        self._chart = PeriodBars()
        wrap = QVBoxLayout()
        wrap.setContentsMargins(12, 4, 18, 14)
        wrap.addWidget(self._chart)
        layout.addLayout(wrap)
        return panel

    def _build_activity_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(
            self._panel_header(
                "Recent activity", "Latest documents and payments — click one to read it"
            )
        )

        # Scrolls rather than growing: this panel sits beside a chart of a
        # fixed height, and a feed that stretched the row would drag the
        # chart's panel down with it.
        self._activity = ActivityList("No activity yet.")
        self._activity.selected.connect(self._on_activity_selected)
        layout.addWidget(self._activity, 1)
        return panel

    def _on_activity_selected(self, record) -> None:
        # An activity entry is a moment in the life of a document, and what
        # someone scanning the feed wants next is the document — so it
        # opens here rather than navigating to the screen it lives on and
        # leaving them to find the row again.
        self._open_card(record.card)

    def _open_card(self, card) -> None:
        RecordCardDialog(card, parent=self).exec()

    def _build_documents_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(
            self._panel_header(
                "Recent documents", "Sales and purchases — open one, or double-click"
                " to find it on its own screen"
            )
        )

        # The same View button the lists carry, in the same last column —
        # this panel is a list of documents like any other.
        actions = RowActionsDelegate([VIEW_ACTION])
        # The shared DataTable, like every other list in the app: same
        # column-width policy, same empty state, same money formatting.
        self._documents_table = DataTable(
            [
                Column("DOCUMENT", lambda r: r.document_no, width=200),
                Column("TYPE", lambda r: r.doc_type, width=110),
                Column("PARTY", lambda r: r.party),
                Column("DATE", lambda r: date_only(r.date), width=140),
                Column("TOTAL", lambda r: money(r.total), align="right", width=130),
                Column("BALANCE", lambda r: money(r.balance), align="right", width=130),
                Column("STATUS", lambda r: r.status, align="center", color=_document_status_color, width=110),
                Column("", lambda _row: "", width=actions.column_width()),
            ],
            placeholder="No sales or purchases recorded yet.",
        )
        actions.setParent(self._documents_table)
        actions.attach(self._documents_table, column=7)
        actions.triggered.connect(self._on_document_action)
        self._documents_table.doubleClicked.connect(self._on_document_double_clicked)
        self._documents_table.fit_to_rows()
        layout.addWidget(self._documents_table)
        return panel

    def _on_document_action(self, _key: str, row_index: int) -> None:
        row = self._documents_table.row_at(row_index)
        if row is not None:
            self._open_card(row.card)

    def _on_document_double_clicked(self, index) -> None:
        row = self._documents_table.row_at(index.row())
        if row is not None:
            self.recordRequested.emit(row.route, row.document_no)

    def _on_loaded(self, data: DashboardData) -> None:
        # The period comes back with the figures rather than being read off
        # the selector here: a load in flight when the choice changes would
        # otherwise label one period's numbers with another's name.
        period = data.period_label.lower()
        self._sales_tile.set_label(f"Sales • {period}")
        self._sales_tile.set_value(pkr(data.sales_total))
        self._sales_tile.set_note(f"{counted(data.sales_count, 'invoice')} issued")
        self._purchases_tile.set_label(f"Purchases • {period}")
        self._purchases_tile.set_value(pkr(data.purchases_total))
        self._purchases_tile.set_note(counted(data.purchases_count, "purchase order"))
        self._low_stock_tile.set_value(str(data.low_stock_count))
        self._render_balance(data, period)

        self._documents_table.set_rows(data.recent_documents)
        self._documents_table.fit_to_rows()

        self._chart.set_buckets(data.buckets)
        self._activity.set_records(data.recent_activity)

    def _render_balance(self, data: DashboardData, period: str) -> None:
        """What is still unpaid, and on which side of the counter.

        Deliberately not netted against each other. The two are owed by
        and to different people: subtracting a supplier's bill from a
        customer's debt produces a number nobody can act on, and hides
        both of the ones they can.
        """
        outstanding = data.receivable + data.payable

        self._balance_tile.set_label(f"Unpaid balances • {period}")
        self._balance_tile.set_value(pkr(outstanding))
        if outstanding:
            self._balance_tile.set_note(
                f"{pkr(data.receivable)} {TO_COLLECT_SHORT}"
                f"   •   {pkr(data.payable)} {TO_PAY_SHORT}"
            )
        else:
            self._balance_tile.set_note(SETTLED)
