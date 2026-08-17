"""
View model for the sales screen: the period-filtered invoice list, the
records the new-sale dialog picks from, and recording a sale.

Mirrors `PurchasesViewModel` — listing is by period and the create dialog
needs items and parties to pick from, so neither fits `CollectionSource`
and both implement the collection contract directly.

Nothing here loads a catalogue. The list names its rows by asking for the
names behind the ids on the page it just received, and the dialog's
pickers ask for matches as they are typed into. Both used to load "up to
five hundred" instead, which is a ceiling a shop grows through without
being told: an invoice for the wrong item, or a line that would not say
what it was.
"""
from __future__ import annotations

from PySide6.QtCore import Signal

from app.application.dto.commands import CreateSaleCommand
from app.application.dto.queries import DocumentPageQuery, PageQuery
from app.container import AppContainer
from app.domain.enums.item_type import ItemType
from app.presentation.formatting import DASH, WALK_IN, payment_method_name
from app.presentation.item_types import PICKER_MATCHES, item_names, search_catalogues
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.viewmodels.document_items import (
    DocumentItemLine,
    ItemCatalogue,
    PaymentLine,
    payment_lines,
)
from app.presentation.widgets.period_selector import PeriodSelection

_METHOD_LIMIT = 200
"""Payment methods are a short list somebody keeps by hand, and every one
of them belongs in the dropdown. A ceiling, not a page size."""


class SalesViewModel(CollectionViewModelBase):
    referenceLoaded = Signal(dict)
    namesLoaded = Signal(object)
    """Names for the page just delivered have landed — the table redraws."""
    catalogueSearched = Signal(object, str, list)  # ItemType, term, records
    partiesSearched = Signal(str, list)  # term, customers

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period
        self._customer_names: dict[int, str] = {}
        self._method_names: dict[int, str] = {}
        self._catalogue = ItemCatalogue()

    # ---------------- listing ----------------

    def build_query(self) -> DocumentPageQuery:
        start, end = self._period.range()
        return DocumentPageQuery(
            **self._state.as_kwargs(),
            start=start,
            end=end,
            payment=self._state.filter_value,
        )

    def fetch(self, query: DocumentPageQuery):
        return self._container.page_sales_use_case().execute(query)

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

    # ---------------- names for the page in hand ----------------

    def load_names_for(self, sales: list) -> None:
        """Fetch what this page's rows and lines point at, and nothing else.

        Two small lookups by id rather than two catalogues: the shop's
        customer list and item list are as long as the shop is old, and
        neither has any bearing on the hundred invoices on screen.
        """
        customer_ids = {
            sale.customer_id
            for sale in sales
            if sale.customer_id and sale.customer_id not in self._customer_names
        }
        item_ids = self._catalogue.missing_ids(sales, ItemType.INVENTORY_ITEM)
        if not customer_ids and not item_ids:
            return

        def fetch() -> dict:
            return {
                "customers": (
                    self._container.customer_names_use_case().execute(customer_ids)
                    if customer_ids
                    else {}
                ),
                "items": item_names(self._container, ItemType.INVENTORY_ITEM, item_ids),
            }

        def _on_success(names: dict) -> None:
            self._customer_names.update(names["customers"])
            self._catalogue.add_names(ItemType.INVENTORY_ITEM, names["items"])
            self.namesLoaded.emit(names)

        self.run_async(fetch, on_success=_on_success)

    # ---------------- what the dialog picks from ----------------

    def load_reference_data(self) -> None:
        """The first page of everything the create dialog offers.

        A dialog opens populated rather than empty; typing into it narrows
        by asking again, so what arrives here is a starting point and not
        the whole of what may be chosen.
        """

        def fetch() -> dict:
            return {
                "customers": self._search_customers(""),
                "payment_methods": (
                    self._container.page_payment_methods_use_case()
                    .execute(PageQuery(page_size=_METHOD_LIMIT))
                    .rows
                ),
                "catalogues": search_catalogues(self._container, ""),
            }

        def _on_success(reference: dict) -> None:
            self._remember(reference)
            self.referenceLoaded.emit(reference)

        self.run_async(fetch, on_success=_on_success)

    def search_catalogue(self, item_type: ItemType, term: str) -> None:
        """Matches for what is being typed into the item picker."""

        def _on_success(records: list) -> None:
            self._catalogue.add_names(
                item_type, {record.id: record.name for record in records}
            )
            self.catalogueSearched.emit(item_type, term, records)

        self.run_async(
            lambda: search_catalogues(self._container, term)[ItemType(item_type)],
            on_success=_on_success,
        )

    def search_parties(self, term: str) -> None:
        """Matches for what is being typed into the customer picker."""

        def _on_success(customers: list) -> None:
            self._customer_names.update({c.id: c.name for c in customers})
            self.partiesSearched.emit(term, customers)

        self.run_async(lambda: self._search_customers(term), on_success=_on_success)

    def _search_customers(self, term: str) -> list:
        return (
            self._container.page_customers_use_case()
            .execute(PageQuery(search=term, page_size=PICKER_MATCHES))
            .rows
        )

    def _remember(self, reference: dict) -> None:
        self._customer_names.update({c.id: c.name for c in reference["customers"]})
        self._method_names = {m.id: m.name for m in reference["payment_methods"]}
        for item_type, records in reference["catalogues"].items():
            self._catalogue.add_names(
                item_type, {record.id: record.name for record in records}
            )

    # ---------------- writing ----------------

    def create(self, command: CreateSaleCommand) -> None:
        use_case = self._container.create_sale_use_case()

        def _on_success(sale) -> None:
            self.itemCreated.emit(sale)
            # Back to the first page, where the new invoice now sorts.
            self.reload_from_start()
            # Stock changed, so what the dialog last offered is stale.
            self.load_reference_data()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)
