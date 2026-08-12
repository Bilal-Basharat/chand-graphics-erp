"""
Profit & loss: did the shop make money in this period, and where it went.

Revenue, less what the stock sold had cost, is gross profit; less what was
spent running the place is net profit. That is the whole screen, in the
order it is read.

Stock *bought* is not in that arithmetic — it sits below with the invoice
discounts as context. Buying paper is not a cost until the paper is sold,
which is the difference between this screen and the "money in, money out"
one it replaces.

Deliberately not a `CollectionView`: this is panels of summary, not a
list. The arithmetic is not here either — see
`app.application.use_cases.reports`, which this only draws.
"""
from __future__ import annotations

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

from app.application.dto.queries import ProfitAndLoss, ReportQuery
from app.container import AppContainer
from app.presentation.dialogs.record_card_dialog import print_card, save_pdf
from app.presentation.formatting import (
    counted,
    date_only,
    money,
    percent,
    uncosted_caveat,
)
from app.presentation.records.builders import profit_and_loss_card
from app.presentation.viewmodels.base import BaseViewModel
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.page_header import PageHeader
from app.presentation.widgets.page_scroll import page_scroll
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.stat_tile import StatTile
from app.presentation.widgets.summary_strip import SummaryStrip
from app.presentation.widgets.table_model import Column

_ZERO = Decimal("0.00")


class ProfitAndLossViewModel(BaseViewModel):
    reportLoaded = Signal(object)  # ProfitAndLoss

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period

    def load(self) -> None:
        start, end = self._period.range()
        query = ReportQuery(start=start, end=end)
        self.run_async(
            lambda: self._container.profit_and_loss_use_case().execute(query),
            on_success=self.reportLoaded.emit,
        )

    @property
    def period_label(self) -> str:
        return self._period.label


class ProfitAndLossView(QWidget):
    def __init__(
        self,
        view_model: ProfitAndLossViewModel,
        period: PeriodSelection,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._period = period
        # What is on screen, kept so it can be put on paper. Nothing to
        # print until the first one arrives.
        self._report: ProfitAndLoss | None = None

        outer = QVBoxLayout(page_scroll(self))
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        header = PageHeader(
            ("Finance", "Profit & loss"),
            "Profit & loss",
            "What was sold, what it cost, and what was left after the bills.",
        )
        selector = PeriodSelector(period)
        selector.periodChanged.connect(self.reload)
        header.add_widget(selector)
        # The same two buttons a record card carries — a report is a
        # record of a period, and it prints through the same page.
        self._save_button = header.add_action("Save as PDF", self._save_pdf)
        self._print_button = header.add_action("Print", self._print, variant="primary")
        for button in (self._save_button, self._print_button):
            button.setEnabled(False)
        outer.addWidget(header)

        self._range_label = QLabel("")
        self._range_label.setProperty("role", "pageSub")
        outer.addWidget(self._range_label)

        outer.addLayout(self._build_tiles())

        # Directly under the figures it qualifies, because a profit that
        # does not know what some of its stock cost is overstated, and
        # that has to be read at the same moment as the profit.
        self._caveat = QLabel("")
        self._caveat.setWordWrap(True)
        self._caveat.setObjectName("uncostedCaveat")
        self._caveat.hide()
        outer.addWidget(self._caveat)

        outer.addWidget(self._build_spending_panel(), 1)

        # Context, visibly outside the arithmetic above. Pushed left
        # against a stretch so two figures stay two figures rather than
        # spreading into a row of banners.
        self._context = SummaryStrip()
        context_row = QHBoxLayout()
        context_row.addWidget(self._context)
        context_row.addStretch(1)
        outer.addLayout(context_row)

        view_model.reportLoaded.connect(self._on_report)
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
        # Four across, in the order the statement is read: what came in,
        # what it cost, what that left, what survived the overheads.
        self._tiles = {
            "revenue": StatTile("Revenue", money(_ZERO), "0 invoices"),
            "cost": StatTile("Cost of goods sold", money(_ZERO), "What the stock cost"),
            "gross": StatTile("Gross profit", money(_ZERO), "Revenue less cost"),
            "net": StatTile("Net profit", money(_ZERO), "After expenses"),
        }
        for index, tile in enumerate(self._tiles.values()):
            grid.addWidget(tile, 0, index)
            grid.setColumnStretch(index, 1)
        return grid

    def _build_spending_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(1, 0, 1, 1)
        layout.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(18, 14, 18, 10)
        title = QLabel("Spending by category")
        title.setProperty("role", "panelTitle")
        self._spending_note = QLabel("")
        self._spending_note.setProperty("role", "panelSub")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self._spending_note)
        layout.addLayout(title_row)

        self._spending = DataTable(
            [
                Column("CATEGORY", lambda row: row.name),
                Column("ENTRIES", lambda row: row.count, align="right", width=110),
                Column("TOTAL", lambda row: money(row.total), align="right", width=160),
                # Read off the row rather than divided here: the use case
                # worked it out where the denominator was known, so the
                # screen and the printed page cannot differ.
                Column("SHARE", lambda row: f"{row.share}%", align="right", width=110),
            ],
            placeholder="Nothing was spent in this period.",
        )
        layout.addWidget(self._spending, 1)
        return panel

    # ---------------- output ----------------

    def _card(self):
        return profit_and_loss_card(self._report, period_label=self._view_model.period_label)

    def _save_pdf(self) -> None:
        if self._report is not None:
            save_pdf(self, self._card())

    def _print(self) -> None:
        if self._report is not None:
            print_card(self, self._card())

    # ---------------- state ----------------

    def _on_report(self, report: ProfitAndLoss) -> None:
        self._report = report
        for button in (self._save_button, self._print_button):
            button.setEnabled(True)

        self._range_label.setText(
            f"{self._view_model.period_label} — "
            f"{date_only(report.start)} to {date_only(report.end)}"
        )

        self._tiles["revenue"].set_value(money(report.revenue))
        self._tiles["revenue"].set_note(counted(report.invoice_count, "invoice"))
        self._tiles["cost"].set_value(money(report.cost_of_goods_sold))
        self._tiles["gross"].set_value(money(report.gross_profit))
        self._tiles["gross"].set_note(f"{percent(report.gross_margin)} margin")
        self._tiles["net"].set_value(money(report.net_profit))
        self._tiles["net"].set_note(
            f"after {money(report.expenses_total)} of expenses"
        )

        caveat = uncosted_caveat(report.uncosted_lines, report.uncosted_revenue)
        self._caveat.setText(caveat)
        self._caveat.setVisible(bool(caveat))

        self._spending.set_rows(list(report.spending))
        self._spending_note.setText(
            counted(len(report.spending), "category", "categories")
        )

        self._context.set_items(
            (
                ("Stock bought", money(report.stock_bought)),
                ("Invoice discounts", money(report.invoice_discounts)),
            )
        )

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "Profit & loss", message)
