"""
Item profitability: which things earned the money, and which only moved it.

A list, unlike its sibling profit & loss screen, so it is built on the
same `CollectionView` every other list uses — one row per item sold in the
period, best earner first.

Revenue here is line totals. An invoice-level discount belongs to the
invoice, not to any one line on it, so it is not apportioned and this
runs a little ahead of the revenue on the profit & loss. The note on the
printed card says so.

An item whose stock was never bought has no cost, and this screen shows a
dash rather than a zero for it — a dash says "not known", a zero would
claim the whole line was profit.
"""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QWidget

from app.application.dto.queries import ItemProfitability, ReportQuery
from app.container import AppContainer
from app.presentation.dialogs.record_card_dialog import print_card, save_pdf
from app.presentation.formatting import counted, money, percent
from app.presentation.records.builders import item_profitability_card
from app.presentation.records.card import RecordCard
from app.presentation.theme import tokens as t
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.views.collection_view import CollectionPage, CollectionView
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.table_model import Column


class ItemProfitabilityViewModel(CollectionViewModelBase):
    """One period's trading, broken down by item.

    Not a `CollectionViewModel`: there is nothing to create, and the rows
    are an aggregate rather than a page of records.
    """

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period
        self._report: ItemProfitability | None = None

    @property
    def report(self) -> ItemProfitability | None:
        """What is on screen, kept so it can be put on paper."""
        return self._report

    @property
    def period_label(self) -> str:
        return self._period.label

    def load(self) -> None:
        start, end = self._period.range()
        query = ReportQuery(start=start, end=end)

        def _on_success(report: ItemProfitability) -> None:
            # Set before the rows go out: the summary strip is rendered
            # from this, off the back of `rowsLoaded`.
            self._report = report
            self.rowsLoaded.emit(list(report.rows))

        self.run_async(
            lambda: self._container.item_profitability_use_case().execute(query),
            on_success=_on_success,
        )

    def search(self, term: str) -> None:
        term = term.strip().lower()
        report = self._report
        if report is None or not term:
            self.load()
            return
        # Filtered from what is already loaded: the period's rows are one
        # per item, so there is nothing to go back to the database for.
        self.rowsLoaded.emit([row for row in report.rows if term in row.name.lower()])


def _profit_color(row) -> str | None:
    if row.profit is None:
        return None
    return t.SUCCESS if row.profit >= 0 else t.DANGER


class ItemProfitabilityView(CollectionView):
    def __init__(
        self,
        view_model: ItemProfitabilityViewModel,
        period: PeriodSelection,
        parent: QWidget | None = None,
    ) -> None:
        self._report_view_model = view_model
        self._period = period

        super().__init__(
            CollectionPage(
                crumb=("Finance", "Item profitability"),
                title="Item profitability",
                subtitle="What each item sold for, what it cost, and what was left.",
                panel_title="Items sold",
                empty_message="Nothing was sold in this period.",
                unit="item",
                search_placeholder="Search by item",
            ),
            [
                Column("ITEM", lambda row: row.name),
                Column(
                    "QTY SOLD",
                    lambda row: f"{row.quantity_sold:,}",
                    align="right",
                    sort_key=lambda row: row.quantity_sold,
                    width=110,
                ),
                Column(
                    "REVENUE",
                    lambda row: money(row.revenue),
                    align="right",
                    sort_key=lambda row: row.revenue,
                    width=140,
                ),
                # `money(None)` is a dash. Deliberate: an item that was
                # never bought has an unknown cost, and a 0.00 here would
                # read as free stock and a perfect margin.
                Column(
                    "COST",
                    lambda row: money(row.cost),
                    align="right",
                    sort_key=lambda row: row.cost if row.cost is not None else 0,
                    width=140,
                ),
                Column(
                    "PROFIT",
                    lambda row: money(row.profit),
                    align="right",
                    color=_profit_color,
                    sort_key=lambda row: row.profit if row.profit is not None else 0,
                    width=140,
                ),
                Column(
                    "MARGIN",
                    lambda row: percent(row.margin),
                    align="right",
                    sort_key=lambda row: row.margin if row.margin is not None else 0,
                    width=110,
                ),
            ],
            view_model,
            parent,
        )

        self._save_button = self._header.add_action("Save as PDF", self._save_pdf)
        self._print_button = self._header.add_action("Print", self._print, variant="primary")
        self._set_paper_enabled(False)

    def toolbar_extras(self) -> list[QWidget]:
        selector = PeriodSelector(self._period)
        selector.periodChanged.connect(self.reload)
        return [selector]

    def summary(self, rows: list) -> Sequence[tuple[str, str]]:
        # The period's figures, not the visible rows': searching narrows
        # what is on screen without changing what the period earned.
        report = self._report_view_model.report
        if report is None:
            return ()
        figures = [
            ("Revenue", money(report.revenue)),
            ("Cost", money(report.cost)),
            ("Profit", money(report.profit)),
            ("Margin", percent(report.margin)),
        ]
        if report.uncosted_lines:
            figures.append(("No cost recorded", counted(report.uncosted_lines, "line")))
        return tuple(figures)

    def on_rows_loaded(self, rows: list) -> None:  # noqa: ARG002 - base contract
        self._set_paper_enabled(self._report_view_model.report is not None)

    # ---------------- paper ----------------

    def _set_paper_enabled(self, enabled: bool) -> None:
        for button in (self._save_button, self._print_button):
            button.setEnabled(enabled)

    def _card(self) -> RecordCard | None:
        report = self._report_view_model.report
        if report is None:
            return None
        return item_profitability_card(
            report, period_label=self._report_view_model.period_label
        )

    def _save_pdf(self) -> None:
        card = self._card()
        if card is not None:
            save_pdf(self, card)

    def _print(self) -> None:
        card = self._card()
        if card is not None:
            print_card(self, card)
