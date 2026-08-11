"""
Account ledger: one party's running balance, read from the top down.

Two screens, one class. A customer ledger and a supplier ledger are the
same statement in opposite directions — what a customer owes you, what
you owe a supplier — so only the wording differs, and that lives in the
`LedgerPage` below rather than in branching inside the view. The same
arrangement as the two payment screens next door.

Which column is the debit is part of that wording. A sale charges a
customer, so it is a debit on their statement; a purchase charges you, so
it is a credit on the supplier's. The balance underneath is worked out
the same way either way — see `app.application.use_cases.ledger`.

The screen is built around picking a party, like the inventory movement
screen is built around picking an item: a ledger is only ever read one
account at a time.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QComboBox, QWidget

from app.application.dto.queries import LedgerLine, LedgerQuery, PartyLedger, SearchQuery
from app.application.ledger.sources import PURCHASE, SALE
from app.container import AppContainer
from app.presentation.dialogs.record_card_dialog import RecordCardDialog, print_card, save_pdf
from app.presentation.formatting import date_time, money, money_or_blank, or_dash
from app.presentation.records.builders import ledger_card
from app.presentation.records.card import RecordCard
from app.presentation.records.documents import (
    DocumentNames,
    purchase_record_card,
    sale_record_card,
)
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.views.collection_view import VIEW_ACTION, CollectionPage, CollectionView
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.table_model import Column

_LIMIT = 500
_NO_PARTIES = "— none yet —"


# ------------------------------------------------- opening what a line came from


@dataclass(frozen=True, slots=True)
class _Document:
    """How to reach the record behind a ledger line, and write it out.

    Keyed by the word the source that produced the line used for it, so a
    ledger fed by more than one family opens each of them correctly
    without the screen knowing which ledger it is drawing.
    """

    fetch: Callable[[AppContainer, str], object | None]
    """By document number: it is what the line already carries, and both
    families are looked up by it everywhere else in the app."""
    card: Callable[[object, str, DocumentNames], RecordCard]


_DOCUMENTS: dict[str, _Document] = {
    SALE: _Document(
        fetch=lambda container, number: (
            container.get_sale_by_invoice_no_use_case().execute(number)
        ),
        card=lambda sale, party, names: sale_record_card(sale, customer=party, names=names),
    ),
    PURCHASE: _Document(
        fetch=lambda container, number: (
            container.get_purchase_by_no_use_case().execute(number)
        ),
        card=lambda purchase, party, names: purchase_record_card(
            purchase, supplier=party, names=names
        ),
    ),
}


# ---------------------------------------------------------------- page copy


@dataclass(frozen=True, slots=True)
class LedgerPage:
    """Everything that differs between the two ledgers.

    Only what genuinely differs. A statement's column headings and its
    closing figure are named the same on both — an account is an account —
    so those are written plainly where they are drawn rather than passed
    through here.
    """

    crumb: tuple[str, ...]
    title: str
    subtitle: str
    empty_message: str
    party_noun: str
    """"Customer" or "Supplier" — the picker's label and the card's."""
    party_placeholder: str
    sides: Callable[[Decimal, Decimal], tuple[Decimal, Decimal]]
    """`(charge, payment) -> (debit, credit)`.

    The whole difference between the two ledgers, as one function. It is
    written this way rather than as two "which column" accessors because
    the flip applies to the totals as much as to the lines, and two
    accessors let those drift apart — which they promptly did.
    """


CUSTOMER_LEDGER_PAGE = LedgerPage(
    crumb=("Parties", "Customer ledger"),
    title="Customer ledger",
    subtitle="One customer's account: what they owed, what they bought, what they paid.",
    empty_message="Choose a customer above to see their account.",
    party_noun="Customer",
    party_placeholder="— choose a customer —",
    # A sale is money they owe you, a receipt is money they have settled.
    sides=lambda charge, payment: (charge, payment),
)

SUPPLIER_LEDGER_PAGE = LedgerPage(
    crumb=("Parties", "Supplier ledger"),
    title="Supplier ledger",
    subtitle="One supplier's account: what you owed, what you bought, what you paid.",
    empty_message="Choose a supplier above to see their account.",
    party_noun="Supplier",
    party_placeholder="— choose a supplier —",
    # The other way round: their bill is what you owe, your payment is
    # what reduces it.
    sides=lambda charge, payment: (payment, charge),
)


# ---------------------------------------------------------------- view models


class AccountLedgerViewModel(CollectionViewModelBase):
    """
    Not a `CollectionViewModel`: listing here is one party's account
    rather than a whole-collection fetch, and the screen also needs the
    list of parties to fill its picker.

    Subclasses supply the two things that differ — which parties, and
    which ledger.
    """

    partiesLoaded = Signal(list)
    documentLoaded = Signal(object)  # RecordCard

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period
        self._party_id: int | None = None
        self._ledger: PartyLedger | None = None

    # -- hooks ------------------------------------------------------------

    def _fetch_parties(self) -> list:
        raise NotImplementedError

    def _fetch_ledger(self, query: LedgerQuery) -> PartyLedger:
        raise NotImplementedError

    # -- shared -----------------------------------------------------------

    @property
    def ledger(self) -> PartyLedger | None:
        """What is on screen, kept so it can be put on paper."""
        return self._ledger

    @property
    def period_label(self) -> str:
        return self._period.label

    def set_party(self, party_id: int | None) -> None:
        self._party_id = party_id

    def load_parties(self) -> None:
        self.run_async(self._fetch_parties, on_success=self.partiesLoaded.emit)

    def load(self) -> None:
        if self._party_id is None:
            # Nothing picked yet — an empty account, not an error.
            self._ledger = None
            self.rowsLoaded.emit([])
            return

        start, end = self._period.range()
        query = LedgerQuery(party_id=self._party_id, start=start, end=end, limit=_LIMIT)

        def _on_success(ledger: PartyLedger) -> None:
            # Set before the rows go out: the summary strip is rendered
            # from this, off the back of `rowsLoaded`.
            self._ledger = ledger
            self.rowsLoaded.emit(list(ledger.lines))

        self.run_async(lambda: self._fetch_ledger(query), on_success=_on_success)

    def search(self, term: str) -> None:  # noqa: ARG002 - scaffold contract, no text search here
        self.load()

    def open_document(self, line: LedgerLine) -> None:
        """Write out the document one line came from.

        Fetched on demand rather than alongside the statement: a period
        can run to hundreds of lines, and the one being read is the one
        that was clicked. The names it needs are read with it, in the same
        trip off the UI thread, because they are three small master-data
        tables and holding them would only mean holding them stale.
        """
        document = _DOCUMENTS.get(line.document_kind)
        ledger = self._ledger
        if document is None or ledger is None or not line.reference:
            return

        def fetch() -> RecordCard | None:
            record = document.fetch(self._container, line.reference)
            if record is None:
                return None
            return document.card(record, ledger.party_name, DocumentNames.load(self._container))

        self.run_async(fetch, on_success=self._on_document_loaded)

    def _on_document_loaded(self, card: RecordCard | None) -> None:
        if card is None:
            # The line is derived from the document, so this means it was
            # deleted while the statement was on screen.
            self.errorOccurred.emit("That document is no longer there. Refresh to see the account as it is now.")
            return
        self.documentLoaded.emit(card)


class CustomerLedgerViewModel(AccountLedgerViewModel):
    def _fetch_parties(self) -> list:
        return self._container.search_customers_use_case().execute(
            SearchQuery(term="", limit=_LIMIT)
        )

    def _fetch_ledger(self, query: LedgerQuery) -> PartyLedger:
        return self._container.get_customer_ledger_use_case().execute(query)


class SupplierLedgerViewModel(AccountLedgerViewModel):
    def _fetch_parties(self) -> list:
        return self._container.search_suppliers_use_case().execute(
            SearchQuery(term="", limit=_LIMIT)
        )

    def _fetch_ledger(self, query: LedgerQuery) -> PartyLedger:
        return self._container.get_supplier_ledger_use_case().execute(query)


# ---------------------------------------------------------------- view


class AccountLedgerView(CollectionView):
    def __init__(
        self,
        page: LedgerPage,
        view_model: AccountLedgerViewModel,
        period: PeriodSelection,
        parent: QWidget | None = None,
    ) -> None:
        self._ledger_page = page
        self._ledger_view_model = view_model
        self._period = period
        # An account asked for from elsewhere, still waiting for the
        # picker to hear about it. See `select_party`.
        self._pending_party_id: int | None = None

        super().__init__(
            CollectionPage(
                crumb=page.crumb,
                title=page.title,
                subtitle=page.subtitle,
                panel_title="Account activity",
                empty_message=page.empty_message,
                unit="entry",
                unit_plural="entries",
            ),
            [
                Column("DATE", lambda line: date_time(line.occurred_at), width=170),
                Column("REFERENCE", lambda line: or_dash(line.reference), width=150),
                Column("DETAIL", lambda line: line.detail),
                Column(
                    "DEBIT",
                    lambda line: money_or_blank(page.sides(line.charge, line.payment)[0]),
                    align="right",
                    width=130,
                ),
                Column(
                    "CREDIT",
                    lambda line: money_or_blank(page.sides(line.charge, line.payment)[1]),
                    align="right",
                    width=130,
                ),
                Column("BALANCE", lambda line: money(line.balance), align="right", width=140),
            ],
            view_model,
            parent,
        )

        # The same two buttons a record card carries — a statement is a
        # record of an account, and it prints through the same page.
        self._save_button = self._header.add_action("Save as PDF", self._save_pdf)
        self._print_button = self._header.add_action("Print", self._print, variant="primary")
        self._set_paper_enabled(False)

        view_model.partiesLoaded.connect(self._on_parties_loaded)
        view_model.documentLoaded.connect(self._show_document)

    def row_actions(self) -> Sequence[RowAction]:
        # The same eye, in the same place, as every other list that shows
        # documents. A statement line is a summary of one, and the first
        # thing asked of a line is what it was for.
        return (VIEW_ACTION,)

    def show_record_card(self, row: object) -> None:
        # Overridden rather than answered through `record_card`: the base
        # opens a card it can build from the row, and this row is not the
        # document — only a line derived from one, which has to be fetched.
        self._ledger_view_model.open_document(row)

    def _show_document(self, card: RecordCard) -> None:
        RecordCardDialog(card, parent=self).exec()

    def create_table(self, columns: Sequence[Column]) -> DataTable:
        # Unsortable on purpose. The balance column is a running total, so
        # it only means anything in date order — sorted by any other
        # column it would read as a sequence of wrong answers.
        return DataTable(columns, placeholder=self._page.empty_message, sortable=False)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Parties are added on other screens during a session, so the
        # picker is refilled on each visit rather than at construction.
        self._ledger_view_model.load_parties()

    def toolbar_extras(self) -> list[QWidget]:
        self._party = QComboBox()
        self._party.setMinimumWidth(260)
        self._party.currentIndexChanged.connect(self._on_party_changed)

        selector = PeriodSelector(self._period)
        selector.periodChanged.connect(self.reload)
        return [self._party, selector]

    def summary(self, rows: list) -> Sequence[tuple[str, str]]:
        # Read from the ledger rather than from `rows`: the opening and
        # closing balances are the account's, not the visible lines'. They
        # stay in step because this screen has no filter and no search —
        # every line the ledger returned is on screen.
        #
        # Opening, what moved, and closing — the four figures a statement
        # is checked against, in the order it is read.
        ledger = self._ledger_view_model.ledger
        if ledger is None:
            return ()
        debit, credit = self._ledger_page.sides(ledger.total_charges, ledger.total_payments)
        return (
            ("Opening balance", money(ledger.opening_balance)),
            ("Debit", money(debit)),
            ("Credit", money(credit)),
            ("Closing balance", money(ledger.closing_balance)),
        )

    def select_party(self, party_id: int) -> None:
        """Show this party's ledger — the way in from the Ledger button on
        the customer and supplier lists.

        The pick is remembered as well as tried, because the party list
        loads off the UI thread: arriving here from another screen almost
        always beats it, and `_on_parties_loaded` honours what was asked
        for when the list finally lands.
        """
        self._pending_party_id = party_id
        index = self._party.findData(party_id)
        if index >= 0:
            self._pending_party_id = None
            self._party.setCurrentIndex(index)

    def on_rows_loaded(self, rows: list) -> None:  # noqa: ARG002 - base contract
        self._set_paper_enabled(self._ledger_view_model.ledger is not None)

    # ---------------- selection ----------------

    def _on_parties_loaded(self, parties: list) -> None:
        # An account asked for from another screen wins; otherwise hold
        # the one the user was already reading across the refresh.
        wanted = self._pending_party_id
        if wanted is None:
            wanted = self._party.currentData()
        self._pending_party_id = None

        self._party.blockSignals(True)
        self._party.clear()
        if parties:
            self._party.addItem(self._ledger_page.party_placeholder, None)
            for party in parties:
                self._party.addItem(party.name, party.id)
        else:
            self._party.addItem(_NO_PARTIES, None)
        chosen = self._party.findData(wanted) if wanted is not None else -1
        self._party.setCurrentIndex(max(chosen, 0))
        self._party.blockSignals(False)

        self._on_party_changed(self._party.currentIndex())

    def _on_party_changed(self, _index: int) -> None:
        self._ledger_view_model.set_party(self._party.currentData())
        self.reload()

    # ---------------- paper ----------------

    def _set_paper_enabled(self, enabled: bool) -> None:
        for button in (self._save_button, self._print_button):
            button.setEnabled(enabled)

    def _card(self) -> RecordCard | None:
        ledger = self._ledger_view_model.ledger
        if ledger is None:
            return None
        return ledger_card(
            ledger,
            party_kind=self._ledger_page.party_noun,
            period_label=self._ledger_view_model.period_label,
            sides=self._ledger_page.sides,
        )

    def _save_pdf(self) -> None:
        card = self._card()
        if card is not None:
            save_pdf(self, card)

    def _print(self) -> None:
        card = self._card()
        if card is not None:
            print_card(self, card)
