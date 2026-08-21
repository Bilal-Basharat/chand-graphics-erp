"""
Purchases screen: period-filtered document list, plus the new-purchase
builder.

Purchases are listed rather than only created, so a paid/partly-paid/
unpaid balance is visible at a glance — that status is the question the
screen exists to answer.
"""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QWidget

from app.application.dto.commands import CreatePurchaseCommand
from app.application.dto.queries import DocumentPageQuery, PageQuery
from app.container import AppContainer
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.new_purchase_dialog import NewPurchaseDialog
from app.presentation.item_types import PICKER_MATCHES, item_names, search_catalogues
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
    ReturnLine,
    payment_lines,
    returns_of,
)
from app.presentation.views.collection_view import VIEW_ACTION, CollectionPage, CollectionView
from app.presentation.views.document_lists import payment_filters
from app.presentation.widgets.grouped_table import GroupedTable
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.table_model import Column, detail_columns

_METHOD_LIMIT = 200
"""Payment methods are a short list somebody keeps by hand, and every one
of them belongs in the dropdown. A ceiling, not a page size."""


class PurchasesViewModel(CollectionViewModelBase):
    """
    Listing is by period, and the create dialog needs items and suppliers
    to pick from, so this doesn't fit `CollectionSource` — it implements
    the collection contract directly instead.

    Nothing here loads a catalogue: the list names its rows from the ids
    on the page it just received, and the dialog's pickers ask for matches
    as they are typed into. Mirrors `SalesViewModel`.
    """

    referenceLoaded = Signal(dict)
    namesLoaded = Signal(object)
    catalogueSearched = Signal(object, str, list)  # ItemType, term, records
    partiesSearched = Signal(str, list)  # term, suppliers

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period
        self._supplier_names: dict[int, str] = {}
        self._method_names: dict[int, str] = {}
        self._catalogue = ItemCatalogue()

    def supplier_name(self, purchase) -> str:
        """The supplier a purchase is from, named either way."""
        if not purchase.supplier_id:
            return NO_SUPPLIER
        # A dash only while the name is still loading — saying "no
        # supplier" there would be a different claim, and a false one.
        return self._supplier_names.get(purchase.supplier_id, DASH)

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

    def return_lines(self, purchase) -> list[ReturnLine]:
        """What went back off one purchase — usually nothing, and then free."""
        return returns_of(
            purchase,
            lambda purchase_id: (
                self._container.list_purchase_returns_use_case().execute(purchase_id)
            ),
            self._catalogue,
        )

    def build_query(self) -> DocumentPageQuery:
        start, end = self._period.range()
        return DocumentPageQuery(
            **self._state.as_kwargs(),
            start=start,
            end=end,
            payment=self._state.filter_value,
        )

    def fetch(self, query: DocumentPageQuery):
        return self._container.page_purchases_use_case().execute(query)

    def load_names_for(self, purchases: list) -> None:
        """Fetch what this page's rows and lines point at, and nothing else."""
        supplier_ids = {
            purchase.supplier_id
            for purchase in purchases
            if purchase.supplier_id and purchase.supplier_id not in self._supplier_names
        }
        item_ids = self._catalogue.missing_ids(purchases, ItemType.INVENTORY_ITEM)
        if not supplier_ids and not item_ids:
            return

        def fetch() -> dict:
            return {
                "suppliers": (
                    self._container.supplier_names_use_case().execute(supplier_ids)
                    if supplier_ids
                    else {}
                ),
                "items": item_names(self._container, ItemType.INVENTORY_ITEM, item_ids),
            }

        def _on_success(names: dict) -> None:
            self._supplier_names.update(names["suppliers"])
            self._catalogue.add_names(ItemType.INVENTORY_ITEM, names["items"])
            self.namesLoaded.emit(names)

        self.run_async(fetch, on_success=_on_success)

    def load_reference_data(self) -> None:
        """The first page of everything the create dialog offers."""

        def fetch() -> dict:
            return {
                "suppliers": self._search_suppliers(""),
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
        """Matches for what is being typed into the supplier picker."""

        def _on_success(suppliers: list) -> None:
            self._supplier_names.update({s.id: s.name for s in suppliers})
            self.partiesSearched.emit(term, suppliers)

        self.run_async(lambda: self._search_suppliers(term), on_success=_on_success)

    def _search_suppliers(self, term: str) -> list:
        return (
            self._container.page_suppliers_use_case()
            .execute(PageQuery(search=term, page_size=PICKER_MATCHES))
            .rows
        )

    def _remember(self, reference: dict) -> None:
        self._supplier_names.update({s.id: s.name for s in reference["suppliers"]})
        self._method_names = {m.id: m.name for m in reference["payment_methods"]}
        for item_type, records in reference["catalogues"].items():
            self._catalogue.add_names(
                item_type, {record.id: record.name for record in records}
            )

    def create(self, command: CreatePurchaseCommand) -> None:
        use_case = self._container.create_purchase_use_case()

        def _on_success(purchase) -> None:
            self.itemCreated.emit(purchase)
            # Back to the first page, where the new purchase now sorts.
            self.reload_from_start()
            # Stock changed, so what the dialog last offered is stale.
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
                Column("PURCHASE #", lambda p: p.purchase_no, sort_field="number", width=160),
                Column("SUPPLIER", view_model.supplier_name, sort_field="supplier"),
                Column(
                    "REFERENCE",
                    lambda p: or_dash(p.reference_no),
                    sort_field="reference",
                    width=150,
                ),
                # No sort on the count: it is the length of a list carried
                # with the row, and the query has no column for it.
                Column("ITEMS", lambda p: len(p.items), align="right", width=80),
                Column("SUBTOTAL", lambda p: money(p.subtotal), align="right", width=140),
                Column(
                    "DISCOUNT",
                    lambda p: money(p.discount_amount),
                    align="right",
                    width=130,
                ),
                Column(
                    "TOTAL",
                    lambda p: money(p.grand_total),
                    align="right",
                    sort_field="total",
                    width=140,
                ),
                Column(
                    "DATE",
                    lambda p: date_time(p.created_at),
                    sort_field="created",
                    width=180,
                ),
            ],
            view_model,
            parent,
        )

        view_model.referenceLoaded.connect(self._on_reference_loaded)
        # Names arrive after the rows that display them.
        view_model.namesLoaded.connect(lambda _names: self.table.refresh())

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
        # See the sale list: returning goods lives on the stock register.
        return (VIEW_ACTION,)

    def record_card(self, row) -> RecordCard:
        return purchase_card(
            row,
            supplier=self._purchases_view_model.supplier_name(row),
            items=self._purchases_view_model.item_lines(row),
            payments=self._purchases_view_model.payment_lines(row),
            returns=self._purchases_view_model.return_lines(row),
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Refreshed on every visit, not just at construction: suppliers and
        # items are created on other screens during the same session, and a
        # dialog offering a stale catalogue is worse than a brief reload.
        self._purchases_view_model.load_reference_data()

    def filter_options(self):
        return payment_filters()

    def summary(self):
        # The period's figures, not this page's — see the sale list.
        result = self.view_model.result
        if result is None or result.totals is None:
            return ()
        return (
            ("Bought", money(result.totals.total)),
            ("Unpaid", money(result.totals.outstanding)),
        )

    def on_rows_loaded(self, rows: list) -> None:
        # The suppliers and items this page points at, by id.
        self._purchases_view_model.load_names_for(rows)

    def toolbar_extras(self) -> list[QWidget]:
        selector = PeriodSelector(self._period)
        # From the start: another period is a different list.
        selector.periodChanged.connect(self.reload_from_start)
        return [selector]

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
