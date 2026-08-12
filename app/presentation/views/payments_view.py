"""
Sale payments and purchase payments: settling what's still owed on a
document that was only part-paid (or not paid at all) when it was created.

Both screens are the same job in opposite directions — money coming in
against an invoice, money going out against a purchase — so the screen and
the dialog are shared, and only the data access differs. That difference
lives in two small view models rather than in branching inside one class.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QWidget

from app.application.dto.commands import (
    RecordPurchasePaymentCommand,
    RecordSalePaymentCommand,
)
from app.application.dto.queries import SearchQuery
from app.container import AppContainer
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.formatting import (
    DASH,
    NO_SUPPLIER,
    WALK_IN,
    date_time,
    money,
    payment_method_name,
)
from app.presentation.item_types import load_catalogues
from app.presentation.records.builders import purchase_card, sale_card
from app.presentation.records.card import RecordCard
from app.presentation.theme import tokens as t
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.viewmodels.document_items import (
    ItemCatalogue,
    PaymentLine,
    payment_lines,
)
from app.presentation.views.collection_view import VIEW_ACTION, CollectionPage, CollectionView
from app.presentation.views.document_lists import NOT_FULLY_PAID, payment_filters
from app.presentation.widgets.grouped_table import GroupedTable
from app.presentation.widgets.input_validation import ZERO, MoneyInput, parse_amount
from app.presentation.widgets.payment_method_combo import PaymentMethodCombo
from app.presentation.widgets.payment_status import payment_status_color, payment_status_text
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.table_model import Column, detail_columns

_REFERENCE_LIMIT = 500


# ---------------------------------------------------------------- view models


class PaymentsViewModel(CollectionViewModelBase):
    """
    Shared behaviour for both payment screens.

    Subclasses supply only the four things that genuinely differ: which
    documents to list, which parties name them, how a payment command is
    built, and which use case records it.
    """

    referenceLoaded = Signal(dict)  # {"parties": [...], "payment_methods": [...]}
    paymentRecorded = Signal(object)

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period
        self._party_names: dict[int, str] = {}
        self._method_names: dict[int, str] = {}

    # -- hooks ------------------------------------------------------------

    def _fetch_documents(self) -> list:
        raise NotImplementedError

    def _fetch_parties(self) -> list:
        raise NotImplementedError

    def _build_command(self, document_id: int, amount: Decimal, method_id: int, reference, note):
        raise NotImplementedError

    def _record(self, command):
        raise NotImplementedError

    def document_number(self, document) -> str:
        raise NotImplementedError

    def party_id(self, document) -> int | None:
        raise NotImplementedError

    def payment_date(self, payment) -> datetime | None:
        raise NotImplementedError

    def record_card(self, document) -> RecordCard:
        """The document written out in full, for the View button."""
        raise NotImplementedError

    def _fetch_catalogues(self) -> dict:
        """Anything else this screen needs to name a document's contents.

        A payment list shows the same records the document lists do, and
        its card has to say the same things about them — so it loads the
        same catalogues. Runs off the UI thread with the rest of the
        reference data.
        """
        return {}

    def _catalogues_loaded(self, reference: dict) -> None:
        """Take up what `_fetch_catalogues` fetched. On the UI thread."""

    @property
    def unnamed_party(self) -> str:
        """What a document with no party attached says instead of nothing."""
        raise NotImplementedError

    # -- shared -----------------------------------------------------------

    def party_name(self, document) -> str:
        """The customer or supplier a document is against, named either way.

        Owned here rather than in the view because the search below matches
        on it — two copies of the lookup would be two chances for the list
        and the filter to disagree about who a document belongs to.
        """
        party_id = self.party_id(document)
        if not party_id:
            return self.unnamed_party
        # A dash only while the name is still loading — naming it a walk-in
        # there would be a different claim, and a false one.
        return self._party_names.get(party_id, DASH)

    def payment_lines(self, document) -> list[PaymentLine]:
        """The instalments behind one document, oldest first."""
        return payment_lines(
            document,
            dated=self.payment_date,
            method_name=lambda method_id: payment_method_name(self._method_names.get(method_id)),
        )

    def load(self) -> None:
        # Everything in the period, in no particular order: which of them
        # to show and in what order is the screen's Filter and Sort, and
        # answering that here as well would be the same rule in two places.
        self.run_async(self._fetch_documents, on_success=self.rowsLoaded.emit)

    def search(self, term: str) -> None:
        term = term.strip().lower()
        if not term:
            self.load()
            return

        def fetch() -> list:
            documents = self._fetch_documents()
            # Matched against the party too: people remember who owes them
            # far more readily than which invoice number it was.
            return [
                d
                for d in documents
                if term in self.document_number(d).lower()
                or term in self.party_name(d).lower()
            ]

        self.run_async(fetch, on_success=self.rowsLoaded.emit)

    def load_reference_data(self) -> None:
        def fetch() -> dict:
            return {
                "parties": self._fetch_parties(),
                "payment_methods": self._container.list_payment_methods_use_case().execute(100),
                **self._fetch_catalogues(),
            }

        def _on_success(reference: dict) -> None:
            self._party_names = {p.id: p.name for p in reference["parties"]}
            self._method_names = {m.id: m.name for m in reference["payment_methods"]}
            self._catalogues_loaded(reference)
            self.referenceLoaded.emit(reference)

        self.run_async(fetch, on_success=_on_success)

    def current_user_id(self) -> int | None:
        user = self._container.current_user_session.get_user()
        return user.user_id if user is not None else None

    def record_payment(
        self,
        document_id: int,
        amount: Decimal,
        payment_method_id: int | None,
        reference_no: str | None,
        note: str | None,
    ) -> None:
        command = self._build_command(document_id, amount, payment_method_id, reference_no, note)

        def _on_success(document) -> None:
            self.paymentRecorded.emit(document)
            self.itemCreated.emit(document)  # closes the dialog (FormDialog contract)
            self.load()

        self.run_async(lambda: self._record(command), on_success=_on_success)


class _ProductCatalogueMixin:
    """The item names a sale or purchase line points at.

    Both payment screens need exactly what their document screen needs,
    and the catalogue that answers it is already shared — so this is the
    two-line wiring, not a second copy of the lookup.
    """

    def _fetch_catalogues(self) -> dict:
        return {"catalogues": load_catalogues(self._container, _REFERENCE_LIMIT)}

    def _catalogues_loaded(self, reference: dict) -> None:
        self._catalogue.set_catalogues(reference["catalogues"])


class SalePaymentsViewModel(_ProductCatalogueMixin, PaymentsViewModel):
    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__(container, period)
        self._catalogue = ItemCatalogue()

    def record_card(self, document) -> RecordCard:
        return sale_card(
            document,
            customer=self.party_name(document),
            items=self._catalogue.lines_of(document),
            payments=self.payment_lines(document),
        )

    def _fetch_documents(self) -> list:
        return self._container.list_sales_by_date_range_use_case().execute(
            self._period.as_query(limit=_REFERENCE_LIMIT)
        )

    def _fetch_parties(self) -> list:
        return self._container.search_customers_use_case().execute(
            SearchQuery(term="", limit=_REFERENCE_LIMIT)
        )

    def _build_command(self, document_id, amount, method_id, reference, note):
        return RecordSalePaymentCommand(
            sale_id=document_id,
            amount=amount,
            payment_method_id=method_id,
            received_by_user_id=self.current_user_id(),
            reference_no=reference,
            note=note,
        )

    def _record(self, command):
        return self._container.record_sale_payment_use_case().execute(command)

    def document_number(self, document) -> str:
        return document.invoice_no

    def party_id(self, document) -> int | None:
        return document.customer_id

    def payment_date(self, payment) -> datetime | None:
        return payment.received_at or payment.created_at

    @property
    def unnamed_party(self) -> str:
        return WALK_IN


class PurchasePaymentsViewModel(_ProductCatalogueMixin, PaymentsViewModel):
    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__(container, period)
        self._catalogue = ItemCatalogue()

    def record_card(self, document) -> RecordCard:
        return purchase_card(
            document,
            supplier=self.party_name(document),
            items=self._catalogue.lines_of(document),
            payments=self.payment_lines(document),
        )

    def _fetch_documents(self) -> list:
        return self._container.list_purchases_by_date_range_use_case().execute(
            self._period.as_query(limit=_REFERENCE_LIMIT)
        )

    def _fetch_parties(self) -> list:
        return self._container.search_suppliers_use_case().execute(
            SearchQuery(term="", limit=_REFERENCE_LIMIT)
        )

    def _build_command(self, document_id, amount, method_id, reference, note):
        return RecordPurchasePaymentCommand(
            purchase_id=document_id,
            amount=amount,
            payment_method_id=method_id,
            paid_by_user_id=self.current_user_id(),
            reference_no=reference,
            note=note,
        )

    def _record(self, command):
        return self._container.record_purchase_payment_use_case().execute(command)

    def document_number(self, document) -> str:
        return document.purchase_no

    def party_id(self, document) -> int | None:
        return document.supplier_id

    def payment_date(self, payment) -> datetime | None:
        return payment.paid_at or payment.created_at

    @property
    def unnamed_party(self) -> str:
        return NO_SUPPLIER


# ---------------------------------------------------------------- view


@dataclass(frozen=True, slots=True)
class PaymentsPage:
    """Wording that differs between the two screens."""

    crumb: tuple[str, ...]
    title: str
    subtitle: str
    panel_title: str
    empty_message: str
    unit: str
    number_header: str
    party_header: str
    search_placeholder: str
    dialog_title: str
    document_noun: str
    amount_caption: str


SALE_PAYMENTS_PAGE = PaymentsPage(
    crumb=("Operations", "Sale payments"),
    title="Sale payments",
    subtitle="What customers still have to pay you, and a place to record it as it comes in.",
    panel_title="Invoices",
    empty_message="Nothing unpaid in this period.",
    unit="invoice",
    number_header="INVOICE #",
    party_header="CUSTOMER",
    search_placeholder="Search by invoice number or customer",
    dialog_title="Record payment received",
    document_noun="invoice",
    amount_caption="Amount received",
)

PURCHASE_PAYMENTS_PAGE = PaymentsPage(
    crumb=("Operations", "Purchase payments"),
    title="Purchase payments",
    subtitle="What you still have to pay suppliers, and a place to record payments as you make them.",
    panel_title="Purchases",
    empty_message="Nothing unpaid in this period.",
    unit="purchase",
    number_header="PURCHASE #",
    party_header="SUPPLIER",
    search_placeholder="Search by purchase number or supplier",
    dialog_title="Record payment made",
    document_noun="purchase",
    amount_caption="Amount paid",
)


def _created(document) -> datetime:
    """Sort key that never trips over a missing timestamp."""
    return document.created_at or datetime.min


class PaymentsView(CollectionView):
    def __init__(
        self,
        page: PaymentsPage,
        view_model: PaymentsViewModel,
        period: PeriodSelection,
        parent: QWidget | None = None,
    ) -> None:
        self._payments_page = page
        self._payments_view_model = view_model
        self._period = period
        self._payment_methods: list = []

        super().__init__(
            CollectionPage(
                crumb=page.crumb,
                title=page.title,
                subtitle=page.subtitle,
                panel_title=page.panel_title,
                empty_message=page.empty_message,
                unit=page.unit,
                search_placeholder=page.search_placeholder,
                create_label="Record payment",
            ),
            [
                Column(page.number_header, view_model.document_number, width=170),
                Column(page.party_header, view_model.party_name),
                Column(
                    "TOTAL",
                    lambda d: money(d.grand_total),
                    align="right",
                    sort_key=lambda d: d.grand_total,
                    width=130,
                ),
                Column(
                    "PAID",
                    lambda d: money(d.paid_amount),
                    align="right",
                    sort_key=lambda d: d.paid_amount,
                    width=130,
                ),
                Column(
                    "BALANCE",
                    lambda d: money(d.balance_amount),
                    align="right",
                    sort_key=lambda d: d.balance_amount,
                    width=130,
                ),
                Column(
                    "STATUS",
                    payment_status_text,
                    align="center",
                    color=payment_status_color,
                    sort_key=lambda d: d.balance_amount,
                    width=110,
                ),
                # Last, like every list in the app: what a document is
                # comes before when it happened.
                Column("DATE", lambda d: date_time(d.created_at), sort_key=_created, width=170),
            ],
            view_model,
            parent,
        )

        # Settling a document is the point of the screen, so the row itself
        # is the control — double-click opens the payment form.
        self.table.doubleClicked.connect(lambda _index: self.open_create_dialog())
        view_model.referenceLoaded.connect(self._on_reference_loaded)

        # This screen exists to get money moved, so it opens on the
        # documents that still need it, biggest first.
        self.table.sorting.sort_by("BALANCE", descending=True)
        if self.filter_box is not None:
            self.filter_box.select(NOT_FULLY_PAID)

    def create_table(self, columns: Sequence[Column]) -> GroupedTable:
        # A document paid in instalments stays one row. Its payments are
        # one disclosure away rather than mixed in beside the debts they
        # settle — see `GroupedTable`.
        page = self._payments_page
        return GroupedTable(
            columns,
            detail_columns(
                columns,
                {
                    page.number_header: ("PAYMENT", lambda p: p.sequence),
                    page.party_header: ("METHOD", lambda p: p.method),
                    "PAID": ("AMOUNT", lambda p: money(p.amount)),
                    "BALANCE": ("BALANCE", lambda p: money(p.balance_after)),
                    "DATE": ("DATE", lambda p: date_time(p.when)),
                },
            ),
            children_of=self._payments_view_model.payment_lines,
            placeholder=page.empty_message,
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._payments_view_model.load_reference_data()

    def filter_options(self):
        return payment_filters()

    def row_actions(self) -> Sequence[RowAction]:
        return (VIEW_ACTION,)

    def record_card(self, row) -> RecordCard:
        return self._payments_view_model.record_card(row)

    def summary(self, rows: list):
        return (
            ("Total", money(sum((d.grand_total for d in rows), ZERO))),
            ("Balance", money(sum((d.balance_amount for d in rows), ZERO))),
        )

    def toolbar_extras(self) -> list[QWidget]:
        selector = PeriodSelector(self._period)
        selector.periodChanged.connect(self.reload)
        return [selector]

    def _on_reference_loaded(self, reference: dict) -> None:
        self._payment_methods = reference["payment_methods"]
        # Party and method names arrive after the rows that display them.
        self.table.refresh()

    def open_create_dialog(self) -> None:
        document = self.table.selected_row()
        if document is None:
            self._payments_view_model.errorOccurred.emit(
                f"Select the {self._payments_page.document_noun} you're recording a payment for."
            )
            return
        if document.balance_amount <= ZERO:
            self._payments_view_model.errorOccurred.emit(
                f"That {self._payments_page.document_noun} is fully paid — nothing left to record."
            )
            return
        RecordPaymentDialog(
            self._payments_view_model,
            page=self._payments_page,
            document=document,
            payment_methods=self._payment_methods,
            parent=self,
        ).exec()


# ---------------------------------------------------------------- dialog


class RecordPaymentDialog(FormDialog):
    def __init__(
        self,
        view_model: PaymentsViewModel,
        *,
        page: PaymentsPage,
        document,
        payment_methods: list,
        parent: QWidget | None = None,
    ) -> None:
        number = view_model.document_number(document)
        super().__init__(
            title=page.dialog_title,
            subtitle=f"{page.document_noun.capitalize()} {number}",
            submit_label="Record payment",
            parent=parent,
        )
        self._view_model = view_model
        self._document = document
        self._balance = document.balance_amount
        self.bind(view_model.itemCreated, view_model.errorOccurred)

        self.add_row("Total", _amount_label(money(document.grand_total)))
        self.add_row("Already paid", _amount_label(money(document.paid_amount)))
        self.add_row("Left to pay", _amount_label(money(self._balance), tone=t.DANGER))

        # Defaulted to the full remaining balance: settling in full is the
        # common case, and a partial payment is a quick edit from there.
        self._amount = MoneyInput(self._balance)
        self.add_row(page.amount_caption, self._amount, required=True)

        self._method = PaymentMethodCombo()
        self._method.set_methods(payment_methods)
        self.add_row("Payment method", self._method)

        self._reference = self.add_row("Reference", QLineEdit())
        self._reference.setPlaceholderText("Cheque or transaction number")

        self._note = self.add_row("Note", QTextEdit())
        self._note.setFixedHeight(56)

        self.add_note(
            f"Recording less than {money(self._balance)} leaves the rest unpaid, "
            "and it stays on this list until it is paid in full."
        )

    def build_command(self) -> tuple | None:
        amount = parse_amount(self._amount.text())
        if amount is None or amount <= ZERO:
            self.reject_with("Enter an amount greater than zero.", self._amount)
            return None
        # Mirrors the use case's own rule so the user hears it immediately
        # rather than after a round trip.
        if amount > self._balance:
            self.reject_with(
                f"That's more than the {money(self._balance)} still to pay.",
                self._amount,
            )
            return None
        if self._view_model.current_user_id() is None:
            self.reject_with("Your session has ended. Sign in again to record a payment.")
            return None

        return (
            amount,
            self._method.method_id,
            self._reference.text().strip() or None,
            self._note.toPlainText().strip() or None,
        )

    def submit_command(self, command: tuple) -> None:
        amount, method_id, reference, note = command
        self._view_model.record_payment(self._document.id, amount, method_id, reference, note)


def _amount_label(text: str, tone: str = t.INK) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {tone}; font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 14px;")
    return label
