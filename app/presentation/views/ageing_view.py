"""
Ageing: what is still owed, and how long it has been owed.

Two screens, one class — money owed to the shop and money the shop owes
are the same question asked of different documents, so only the wording
differs and that lives in the `AgeingPage` below. The same arrangement as
the two ledgers and the two payment screens.

There is no period selector here, and that is not an omission. An ageing
report is a snapshot: everything unpaid *as at now*, whenever it was
raised. A period would hide the oldest debts, which are the ones the
screen exists to show.

Age is counted from the day the document was raised, not from a due date.
Nothing in this app records payment terms, so "overdue" is a claim it
cannot make — see `app.application.use_cases.reports.AGE_BANDS`.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from app.application.dto.queries import Ageing, AgeingQuery, PageResult
from app.container import AppContainer
from app.presentation.dialogs.record_card_dialog import print_card, save_pdf
from app.presentation.formatting import counted, date_only, date_time, money
from app.presentation.records.builders import ageing_card
from app.presentation.records.card import RecordCard
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.views.collection_view import CollectionPage, CollectionView
from app.presentation.widgets.table_model import Column
from app.shared.datetimes import now_pkt


# ---------------------------------------------------------------- page copy


@dataclass(frozen=True, slots=True)
class AgeingPage:
    """Everything that differs between the two ageing screens.

    Only what genuinely differs. The bands, the columns and the way an age
    is worked out are the same on both — a debt is a debt — so those are
    written plainly where they are drawn.
    """

    crumb: tuple[str, ...]
    title: str
    panel_title: str
    empty_message: str
    party_header: str
    reference_header: str
    search_placeholder: str


RECEIVABLES_PAGE = AgeingPage(
    crumb=("Finance", "Receivables ageing"),
    title="Receivables ageing",
    panel_title="Unpaid invoices",
    empty_message="Nothing is owed to you.",
    party_header="CUSTOMER",
    reference_header="INVOICE #",
    search_placeholder="Search by customer or invoice number",
)

PAYABLES_PAGE = AgeingPage(
    crumb=("Finance", "Payables ageing"),
    title="Payables ageing",
    panel_title="Unpaid bills",
    empty_message="You owe nothing.",
    party_header="SUPPLIER",
    reference_header="PURCHASE #",
    search_placeholder="Search by supplier or purchase number",
)


# ---------------------------------------------------------------- view model

_SORT_KEYS = {
    "party": lambda line: line.party.lower(),
    "reference": lambda line: line.reference.lower(),
    "raised": lambda line: line.occurred_at,
    "age": lambda line: line.age_days,
    "band": lambda line: line.age_days,
    "outstanding": lambda line: line.outstanding,
}
"""Ordered here rather than by the database: this screen holds every
unpaid document at once, so the whole list is in hand to sort. The band
sorts by age, not alphabetically — "90+" comes after "31-60"."""


class AgeingViewModel(CollectionViewModelBase):
    """Everything unpaid, as at now.

    Subclasses supply the one thing that differs — which use case answers.
    The same arrangement as the two ledger view models.
    """

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container
        self._report: Ageing | None = None

    def _fetch(self, query: AgeingQuery) -> Ageing:
        raise NotImplementedError

    @property
    def report(self) -> Ageing | None:
        """What is on screen, kept so it can be put on paper."""
        return self._report

    def fetch(self, query) -> PageResult:
        """Everything unpaid, as one page.

        Not paged, and deliberately: the bands and the total along the top
        are computed across every unpaid document, so a page of the lines
        would leave the figures describing something the rows do not. The
        set is naturally small — it is only what is owed.
        """
        report = self._fetch(AgeingQuery(as_at=now_pkt()))
        # Set here rather than when the rows arrive because the summary
        # strip is drawn from it the moment they do.
        self._report = report

        term = query.search.lower()
        lines = [
            line
            for line in report.lines
            if not term or term in line.party.lower() or term in line.reference.lower()
        ]
        key = _SORT_KEYS.get(query.sort_field or "")
        if key is not None:
            lines.sort(key=key, reverse=query.sort_desc)
        return PageResult(rows=lines, total=len(lines), page=1, page_size=max(1, len(lines)))


class ReceivablesAgeingViewModel(AgeingViewModel):
    def _fetch(self, query: AgeingQuery) -> Ageing:
        return self._container.receivables_ageing_use_case().execute(query)


class PayablesAgeingViewModel(AgeingViewModel):
    def _fetch(self, query: AgeingQuery) -> Ageing:
        return self._container.payables_ageing_use_case().execute(query)


# ---------------------------------------------------------------- view


class AgeingView(CollectionView):
    def __init__(
        self,
        page: AgeingPage,
        view_model: AgeingViewModel,
        parent: QWidget | None = None,
    ) -> None:
        self._ageing_page = page
        self._ageing_view_model = view_model

        super().__init__(
            CollectionPage(
                crumb=page.crumb,
                title=page.title,
                panel_title=page.panel_title,
                empty_message=page.empty_message,
                unit="document",
                search_placeholder=page.search_placeholder,
            ),
            [
                Column(page.party_header, lambda line: line.party, sort_field="party"),
                Column(
                    page.reference_header,
                    lambda line: line.reference,
                    sort_field="reference",
                    width=150,
                ),
                Column(
                    "RAISED",
                    lambda line: date_time(line.occurred_at),
                    sort_field="raised",
                    width=170,
                ),
                Column(
                    "AGE",
                    lambda line: counted(line.age_days, "day"),
                    align="right",
                    sort_field="age",
                    width=110,
                ),
                Column("BAND", lambda line: line.band, sort_field="band", width=130),
                Column(
                    "OUTSTANDING",
                    lambda line: money(line.outstanding),
                    align="right",
                    sort_field="outstanding",
                    width=150,
                ),
            ],
            view_model,
            parent,
        )

        # Opens oldest first, which is the order these get chased in.
        self.set_initial_sort("AGE", descending=True)

        self._save_button = self._header.add_action("Save as PDF", self._save_pdf)
        self._print_button = self._header.add_action("Print", self._print, variant="primary")
        self._set_paper_enabled(False)

    def summary(self) -> Sequence[tuple[str, str]]:
        # Every band, always — including the empty ones, so the strip does
        # not change shape as debts move between bands.
        report = self._ageing_view_model.report
        if report is None:
            return ()
        # "As at" leads, because every figure after it is only true at
        # that moment — this screen has no period, so the date is the one
        # thing that qualifies the rest.
        return (
            ("As at", date_only(report.as_at)),
            *((band.label, money(band.total)) for band in report.bands),
            ("Total", money(report.total)),
        )

    def on_rows_loaded(self, rows: list) -> None:  # noqa: ARG002 - base contract
        self._set_paper_enabled(self._ageing_view_model.report is not None)

    # ---------------- paper ----------------

    def _set_paper_enabled(self, enabled: bool) -> None:
        for button in (self._save_button, self._print_button):
            button.setEnabled(enabled)

    def _card(self) -> RecordCard | None:
        report = self._ageing_view_model.report
        if report is None:
            return None
        return ageing_card(
            report,
            title=self._ageing_page.title,
            party_noun=self._ageing_page.party_header.capitalize(),
        )

    def _save_pdf(self) -> None:
        card = self._card()
        if card is not None:
            save_pdf(self, card)

    def _print(self) -> None:
        card = self._card()
        if card is not None:
            print_card(self, card)
