"""
View model for the sales screen: the period-filtered invoice list, the
catalogues the new-sale dialog picks from, and recording a sale.

Mirrors `PurchasesViewModel` — listing is by date range and the create
dialog needs the item catalogues, so neither fits `CollectionSource` and
both implement the collection contract directly.
"""
from __future__ import annotations

from PySide6.QtCore import Signal

from app.application.dto.commands import CreateSaleCommand
from app.application.dto.queries import SearchQuery
from app.container import AppContainer
from app.presentation.formatting import DASH, WALK_IN, payment_method_name
from app.presentation.item_types import load_catalogues
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.viewmodels.document_items import (
    DocumentItemLine,
    ItemCatalogue,
    PaymentLine,
    payment_lines,
)
from app.presentation.widgets.period_selector import PeriodSelection

_REFERENCE_LIMIT = 500
_SEARCH_LIMIT = 200


class SalesViewModel(CollectionViewModelBase):
    referenceLoaded = Signal(dict)

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period
        self._customer_names: dict[int, str] = {}
        self._method_names: dict[int, str] = {}
        self._catalogue = ItemCatalogue()

    # ---------------- listing ----------------

    def load(self) -> None:
        use_case = self._container.list_sales_by_date_range_use_case()
        self.run_async(
            lambda: use_case.execute(self._period.as_query()),
            on_success=self.rowsLoaded.emit,
        )

    def search(self, term: str) -> None:
        term = term.strip()
        if not term:
            self.load()
            return
        use_case = self._container.search_sales_use_case()
        self.run_async(
            lambda: use_case.execute(SearchQuery(term=term, limit=_SEARCH_LIMIT)),
            on_success=self.rowsLoaded.emit,
        )

    def customer_name(self, sale) -> str:
        """The customer an invoice is against, named either way."""
        if not sale.customer_id:
            return WALK_IN
        # A dash only for a customer whose name hasn't arrived yet — saying
        # "walk-in" there would be a different claim, and a false one.
        return self._customer_names.get(sale.customer_id, DASH)

    def item_lines(self, sale) -> list[DocumentItemLine]:
        """What was sold on one invoice, ready to read underneath it."""
        return self._catalogue.lines_of(sale)

    def payment_lines(self, sale) -> list[PaymentLine]:
        """What has been paid against one invoice, oldest first."""
        return payment_lines(
            sale,
            dated=lambda payment: payment.received_at or payment.created_at,
            method_name=lambda method_id: payment_method_name(self._method_names.get(method_id)),
        )

    # ---------------- reference data ----------------

    def load_reference_data(self) -> None:
        """One round trip for everything the create dialog needs."""

        def fetch() -> dict:
            return {
                "customers": self._container.search_customers_use_case().execute(
                    SearchQuery(term="", limit=_REFERENCE_LIMIT)
                ),
                "payment_methods": self._container.list_payment_methods_use_case().execute(100),
                "catalogues": load_catalogues(self._container, _REFERENCE_LIMIT),
            }

        def _on_success(reference: dict) -> None:
            self._customer_names = {c.id: c.name for c in reference["customers"]}
            self._method_names = {m.id: m.name for m in reference["payment_methods"]}
            self._catalogue.set_catalogues(reference["catalogues"])
            self.referenceLoaded.emit(reference)

        self.run_async(fetch, on_success=_on_success)

    # ---------------- writing ----------------

    def create(self, command: CreateSaleCommand) -> None:
        use_case = self._container.create_sale_use_case()

        def _on_success(sale) -> None:
            self.itemCreated.emit(sale)
            self.load()
            # Stock changed, so the dialog's catalogues are now stale.
            self.load_reference_data()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)
