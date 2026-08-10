"""
Purchases screen: period-filtered document list, plus the new-purchase
builder.

Purchases are listed rather than only created, so a paid/partly-paid/
unpaid balance is visible at a glance — that status is the question the
screen exists to answer.
"""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QWidget

from app.application.dto.commands import CreatePurchaseCommand
from app.application.dto.queries import SearchQuery
from app.container import AppContainer
from app.presentation.dialogs.new_purchase_dialog import NewPurchaseDialog
from app.presentation.item_types import load_catalogues
from app.presentation.formatting import (
    DASH,
    NO_SUPPLIER,
    date_time,
    money,
    or_dash,
    payment_method_name,
)
from app.presentation.records.builders import purchase_card
from app.presentation.records.card import RecordCard
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.viewmodels.document_items import (
    DocumentItemLine,
    ItemCatalogue,
    PaymentLine,
    payment_lines,
)
from app.presentation.views.collection_view import VIEW_ACTION, CollectionPage, CollectionView
from app.presentation.views.document_lists import created_at, payment_filters
from app.presentation.widgets.grouped_table import GroupedTable
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.table_model import Column, detail_columns

_REFERENCE_LIMIT = 500
_ZERO = Decimal("0.00")


class PurchasesViewModel(CollectionViewModelBase):
    """
    Listing is by date range, and the create dialog needs several
    catalogues, so this doesn't fit `CollectionSource` — it implements the
    collection contract directly instead.
    """

    referenceLoaded = Signal(dict)

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period
        self._method_names: dict[int, str] = {}
        self._catalogue = ItemCatalogue()

    def item_lines(self, purchase) -> list[DocumentItemLine]:
        """What was bought on one purchase, ready to read underneath it."""
        return self._catalogue.lines_of(purchase)

    def payment_lines(self, purchase) -> list[PaymentLine]:
        """What has been paid against one purchase, oldest first."""
        return payment_lines(
            purchase,
            dated=lambda payment: payment.paid_at or payment.created_at,
            method_name=lambda method_id: payment_method_name(self._method_names.get(method_id)),
        )

    def load(self) -> None:
        use_case = self._container.list_purchases_by_date_range_use_case()
        self.run_async(
            lambda: use_case.execute(self._period.as_query()),
            on_success=self.rowsLoaded.emit,
        )

    def search(self, term: str) -> None:
        term = term.strip()
        if not term:
            self.load()
            return
        use_case = self._container.search_purchases_use_case()
        self.run_async(
            lambda: use_case.execute(SearchQuery(term=term, limit=200)),
            on_success=self.rowsLoaded.emit,
        )

    def load_reference_data(self) -> None:
        """One round trip for everything the create dialog needs."""

        def fetch() -> dict:
            return {
                "suppliers": self._container.search_suppliers_use_case().execute(
                    SearchQuery(term="", limit=_REFERENCE_LIMIT)
                ),
                "payment_methods": self._container.list_payment_methods_use_case().execute(100),
                "catalogues": load_catalogues(self._container, _REFERENCE_LIMIT),
            }

        def _on_success(reference: dict) -> None:
            self._method_names = {m.id: m.name for m in reference["payment_methods"]}
            self._catalogue.set_catalogues(reference["catalogues"])
            self.referenceLoaded.emit(reference)

        self.run_async(fetch, on_success=_on_success)

    def create(self, command: CreatePurchaseCommand) -> None:
        use_case = self._container.create_purchase_use_case()

        def _on_success(purchase) -> None:
            self.itemCreated.emit(purchase)
            self.load()
            # Stock changed, so the dialog's catalogues are now stale.
            self.load_reference_data()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)


class PurchasesView(CollectionView):
    def __init__(
        self,
        view_model: PurchasesViewModel,
        period: PeriodSelection,
        current_user_id_provider,
        parent: QWidget | None = None,
    ) -> None:
        self._period = period
        self._purchases_view_model = view_model
        self._current_user_id_provider = current_user_id_provider
        self._reference: dict = {}

        super().__init__(
            CollectionPage(
                crumb=("Operations", "Purchases"),
                title="Purchases",
                subtitle="Stock bought in, what it cost, and what is still to pay.",
                panel_title="Purchase list",
                empty_message="No purchases in this period.",
                unit="purchase",
                unit_plural="purchases",
                search_placeholder="Search by purchase number, supplier or reference",
                create_label="New purchase",
            ),
            # See the sale list for why Paid/Unpaid/Status aren't here:
            # they are the purchase payments screen's whole subject, and
            # carrying them here as well left no room for the item names.
            [
                Column("PURCHASE #", lambda p: p.purchase_no, width=160),
                Column("SUPPLIER", self._supplier_label),
                Column("REFERENCE", lambda p: or_dash(p.reference_no), width=150),
                Column(
                    "ITEMS",
                    lambda p: len(p.items),
                    align="right",
                    sort_key=lambda p: len(p.items),
                    width=80,
                ),
                Column(
                    "SUBTOTAL",
                    lambda p: money(p.subtotal),
                    align="right",
                    sort_key=lambda p: p.subtotal,
                    width=140,
                ),
                Column(
                    "DISCOUNT",
                    lambda p: money(p.discount_amount),
                    align="right",
                    sort_key=lambda p: p.discount_amount,
                    width=130,
                ),
                Column(
                    "TOTAL",
                    lambda p: money(p.grand_total),
                    align="right",
                    sort_key=lambda p: p.grand_total,
                    width=140,
                ),
                Column("DATE", lambda p: date_time(p.created_at), sort_key=created_at, width=180),
            ],
            view_model,
            parent,
        )

        view_model.referenceLoaded.connect(self._on_reference_loaded)

    def create_table(self, columns: Sequence[Column]) -> GroupedTable:
        # A purchase stays one row carrying its own totals; what was bought
        # on it is one disclosure away. Written as "what goes under which
        # heading" so the two rows can't drift apart — see `detail_columns`.
        return GroupedTable(
            columns,
            detail_columns(
                columns,
                {
                    # The item name goes in the widest column there is, so
                    # a long one still fits on the line.
                    "SUPPLIER": ("ITEM", lambda line: line.label),
                    "REFERENCE": ("", lambda _line: ""),
                    "ITEMS": ("QTY", lambda line: line.quantity),
                    "SUBTOTAL": ("UNIT PRICE", lambda line: money(line.unit_price)),
                    "DISCOUNT": ("", lambda _line: ""),
                    "TOTAL": ("LINE TOTAL", lambda line: money(line.total)),
                },
            ),
            children_of=self._purchases_view_model.item_lines,
            placeholder="No purchases in this period.",
        )

    def row_actions(self) -> Sequence[RowAction]:
        return (VIEW_ACTION,)

    def record_card(self, row) -> RecordCard:
        return purchase_card(
            row,
            supplier=self._supplier_label(row),
            items=self._purchases_view_model.item_lines(row),
            payments=self._purchases_view_model.payment_lines(row),
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Refreshed on every visit, not just at construction: suppliers and
        # items are created on other screens during the same session, and a
        # dialog offering a stale catalogue is worse than a brief reload.
        self._purchases_view_model.load_reference_data()

    def filter_options(self):
        return payment_filters()

    def summary(self, rows: list):
        return (
            ("Bought", money(sum((p.grand_total for p in rows), _ZERO))),
            ("Unpaid", money(sum((p.balance_amount for p in rows), _ZERO))),
        )

    def toolbar_extras(self) -> list[QWidget]:
        selector = PeriodSelector(self._period)
        selector.periodChanged.connect(self.reload)
        return [selector]

    def _supplier_label(self, purchase) -> str:
        """The supplier a purchase is from, named either way."""
        if not purchase.supplier_id:
            return NO_SUPPLIER
        for supplier in self._reference.get("suppliers", []):
            if supplier.id == purchase.supplier_id:
                return supplier.name
        # A dash only while the name is still loading — saying "no
        # supplier" there would be a different claim, and a false one.
        return DASH

    def _on_reference_loaded(self, reference: dict) -> None:
        self._reference = reference
        self.table.refresh()  # supplier names resolve now that they're loaded

    def open_create_dialog(self) -> None:
        if not self._reference:
            self._purchases_view_model.errorOccurred.emit(
                "Still loading suppliers and items — try again in a moment."
            )
            return
        NewPurchaseDialog(
            self._purchases_view_model,
            suppliers=self._reference["suppliers"],
            payment_methods=self._reference["payment_methods"],
            catalogues=self._reference["catalogues"],
            current_user_id=self._current_user_id_provider(),
            parent=self,
        ).exec()
