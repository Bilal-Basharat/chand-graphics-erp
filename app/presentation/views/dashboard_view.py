"""
Dashboard screen: KPI tiles, chart placeholder, recent activity, recent
documents. Purely rendering — all data comes from DashboardViewModel.

This is the one screen whose content is taller than the window rather than
a single table that stretches to fit, so it owns a page scroller. Without
it the last panel — recent documents — was simply cut off by the bottom of
the window, and the rows it did show sat behind a scrollbar of their own.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.presentation.theme import tokens as t
from app.presentation.viewmodels.dashboard_viewmodel import DashboardData, DashboardViewModel
from app.presentation.formatting import date_only, money
from app.presentation.widgets.activity_list import ActivityList
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.monthly_bars import MonthlyBars
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
    def __init__(self, view_model: DashboardViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._loaded_once = False

        scroll = QScrollArea(self)
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("PageScrollBody")
        scroll.setWidget(body)

        frame = QVBoxLayout(self)
        frame.setContentsMargins(0, 0, 0, 0)
        frame.addWidget(scroll)

        outer = QVBoxLayout(body)
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
        self._sales_tile = StatTile("Sales this month", "PKR 0")
        self._purchases_tile = StatTile("Purchases this month", "PKR 0")
        self._low_stock_tile = StatTile("Low stock items", "0", "Below minimum stock level")
        self._pending_tile = StatTile("Pending balances", "PKR 0")
        for tile in (self._sales_tile, self._purchases_tile, self._low_stock_tile, self._pending_tile):
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
        layout.addLayout(self._panel_header("Sales vs purchases", "Last 12 months, PKR"))

        self._chart = MonthlyBars()
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
            self._panel_header("Recent activity", "Latest documents and payments")
        )

        # Scrolls rather than growing: this panel sits beside a chart of a
        # fixed height, and a feed that stretched the row would drag the
        # chart's panel down with it.
        self._activity = ActivityList("No activity yet.")
        layout.addWidget(self._activity, 1)
        return panel

    def _build_documents_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._panel_header("Recent documents", "Sales and purchase documents"))

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
            ],
            placeholder="No sales or purchases recorded yet.",
        )
        self._documents_table.fit_to_rows()
        layout.addWidget(self._documents_table)
        return panel

    def _on_loaded(self, data: DashboardData) -> None:
        self._sales_tile.set_value(f"PKR {data.sales_total:,.0f}")
        self._sales_tile.set_note(f"{data.sales_count} invoices issued")
        self._purchases_tile.set_value(f"PKR {data.purchases_total:,.0f}")
        self._purchases_tile.set_note(f"{data.purchases_count} purchase orders")
        self._low_stock_tile.set_value(str(data.low_stock_count))
        self._pending_tile.set_value(f"PKR {data.pending_balance:,.0f}")
        self._pending_tile.set_note(f"Across {data.pending_parties} parties")

        self._documents_table.set_rows(data.recent_documents)
        self._documents_table.fit_to_rows()

        self._chart.set_months(data.monthly)
        self._activity.set_records(data.recent_activity)
