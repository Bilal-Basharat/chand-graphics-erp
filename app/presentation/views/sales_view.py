"""
Sales screen: period-filtered invoice list, plus the new-sale builder.

Read alongside `purchases_view.py` — the two are the same screen in
opposite directions, and are built the same way so that they can be. Each
invoice opens to show what was sold on it, which is the question a list
of totals otherwise can't answer without leaving the screen.
"""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QWidget

from app.presentation.dialogs.new_sale_dialog import NewSaleDialog
from app.presentation.formatting import date_time, money
from app.presentation.records.builders import sale_card
from app.presentation.records.card import RecordCard
from app.presentation.viewmodels.sales_viewmodel import SalesViewModel
from app.presentation.views.collection_view import VIEW_ACTION, CollectionPage, CollectionView
from app.presentation.views.document_lists import payment_filters
from app.presentation.widgets.grouped_table import GroupedTable
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.table_model import Column, detail_columns


class SalesView(CollectionView):
    def __init__(
        self,
        view_model: SalesViewModel,
        period: PeriodSelection,
        current_user_id_provider,
        parent: QWidget | None = None,
    ) -> None:
        self._period = period
        self._sales_view_model = view_model
        self._current_user_id_provider = current_user_id_provider
        self._reference: dict = {}

        super().__init__(
            CollectionPage(
                crumb=("Operations", "Sales"),
                title="Sales",
                subtitle="Invoices raised, what they came to, and what is still unpaid.",
                panel_title="Sale list",
                empty_message="No sales in this period.",
                unit="sale",
                search_placeholder="Search by invoice number or customer",
                create_label="New sale",
            ),
            # What a sale *is*, and what it came to. How far it has been
            # paid lives on the sale payments screen, which exists for
            # exactly that question — carrying Paid/Unpaid/Status here too
            # squeezed the customer's name down to nothing.
            [
                Column("INVOICE #", lambda s: s.invoice_no, sort_field="invoice", width=160),
                Column("CUSTOMER", view_model.customer_name, sort_field="customer"),
                # No sort on the count: it is the length of a list carried
                # with the row, and the query has no column for it.
                Column("ITEMS", lambda s: len(s.items), align="right", width=80),
                # Subtotal and discount are shown, not implied: without
                # them the item lines underneath add up to a figure the
                # TOTAL column doesn't match, and the gap looks like a bug.
                Column("SUBTOTAL", lambda s: money(s.subtotal), align="right", width=140),
                Column(
                    "DISCOUNT",
                    lambda s: money(s.discount_amount),
                    align="right",
                    width=130,
                ),
                Column(
                    "TOTAL",
                    lambda s: money(s.grand_total),
                    align="right",
                    sort_field="total",
                    width=140,
                ),
                Column(
                    "DATE",
                    lambda s: date_time(s.created_at),
                    sort_field="created",
                    width=180,
                ),
            ],
            view_model,
            parent,
        )

        view_model.referenceLoaded.connect(self._on_reference_loaded)
        # Names arrive after the rows that display them, both for the page
        # just loaded and for whatever the dialog last searched.
        view_model.namesLoaded.connect(lambda _names: self.table.refresh())

    def create_table(self, columns: Sequence[Column]) -> GroupedTable:
        # An invoice stays one row carrying its own totals; what was sold on
        # it is one disclosure away. Written as "what goes under which
        # heading" so the two rows can't drift apart — see `detail_columns`.
        return GroupedTable(
            columns,
            detail_columns(
                columns,
                {
                    "CUSTOMER": ("ITEM", lambda line: line.label),
                    "ITEMS": ("QTY", lambda line: line.quantity),
                    "SUBTOTAL": ("UNIT PRICE", lambda line: money(line.unit_price)),
                    "DISCOUNT": ("", lambda _line: ""),
                    "TOTAL": ("LINE TOTAL", lambda line: money(line.total)),
                },
            ),
            children_of=self._sales_view_model.item_lines,
            placeholder="No sales in this period.",
        )

    def row_actions(self) -> Sequence[RowAction]:
        return (VIEW_ACTION,)

    def record_card(self, row) -> RecordCard:
        return sale_card(
            row,
            customer=self._sales_view_model.customer_name(row),
            items=self._sales_view_model.item_lines(row),
            payments=self._sales_view_model.payment_lines(row),
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Refreshed on every visit, not just at construction: customers and
        # items are created on other screens during the same session,
        # and a dialog offering a stale catalogue is worse than a reload.
        self._sales_view_model.load_reference_data()

    def filter_options(self):
        return payment_filters()

    def summary(self):
        # The period's figures, not this page's. Added up from the rows on
        # screen they would report a hundredth of the month under a caption
        # claiming the month — wrong, and never failing.
        result = self.view_model.result
        if result is None or result.totals is None:
            return ()
        return (
            ("Sold", money(result.totals.total)),
            ("Unpaid", money(result.totals.outstanding)),
        )

    def on_rows_loaded(self, rows: list) -> None:
        # The customers and items this page points at, by id — never a
        # catalogue, which is a ceiling a shop grows through.
        self._sales_view_model.load_names_for(rows)

    def toolbar_extras(self) -> list[QWidget]:
        selector = PeriodSelector(self._period)
        # From the start: another period is a different list, and page
        # seven of it may not exist.
        selector.periodChanged.connect(self.reload_from_start)
        return [selector]

    def _on_reference_loaded(self, reference: dict) -> None:
        self._reference = reference
        # Customer and product names arrive after the rows that display them.
        self.table.refresh()

    def open_create_dialog(self) -> None:
        if not self._reference:
            self._sales_view_model.errorOccurred.emit(
                "Still loading customers and items — try again in a moment."
            )
            return
        NewSaleDialog(
            self._sales_view_model,
            customers=self._reference["customers"],
            payment_methods=self._reference["payment_methods"],
            catalogues=self._reference["catalogues"],
            current_user_id=self._current_user_id_provider(),
            parent=self,
        ).exec()
