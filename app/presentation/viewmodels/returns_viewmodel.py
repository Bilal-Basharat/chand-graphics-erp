"""
What the return dialog needs, wherever it was opened from.

Its own view model rather than three methods bolted onto the sales,
purchases and stock screens: all three open the same dialog, and a return
recorded from one of them has to behave identically to one recorded from
another. The screen that opened it is told afterwards through
`returnRecorded` and reloads whatever it was showing.

Two subclasses, differing in three private hooks — the same arrangement
as the two payment screens. A sale return and a purchase return are the
same act in opposite directions, and everything shared is written once
above them.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal

from app.application.dto.queries import (
    DocumentPageQuery,
    ReturnableDocument,
    ReturnableDocumentQuery,
)
from app.container import AppContainer
from app.presentation.viewmodels.base import BaseViewModel

MATCHES = 50
"""How many documents the picker offers as it is typed into. A shortlist
to choose from, not a page to read — past this, the answer is more
typing."""

_ALL_TIME = (datetime(2000, 1, 1), datetime(2999, 12, 31))
"""The window the picker searches.

A return is not a period question: a customer can bring something back
that was bought two years ago, and a picker that quietly only offered
this month's invoices would look like the invoice had been deleted.
"""


class ReturnsViewModel(BaseViewModel):
    documentsSearched = Signal(str, list)
    """term, [(reference, document id)] — matches for the picker."""

    documentResolved = Signal(object)
    """A `ReturnableDocument`: its lines, and how much of each is left."""

    returnRecorded = Signal(object)
    """The return that was written. The screen behind the dialog reloads
    on this, and the dialog closes."""

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container

    # ---------------- what each kind does ----------------

    def _search(self, term: str) -> list[tuple[str, int]]:
        raise NotImplementedError

    def _resolve(self, request: ReturnableDocumentQuery) -> ReturnableDocument:
        raise NotImplementedError

    def _record(self, command):
        raise NotImplementedError

    # ---------------- shared ----------------

    def search_documents(self, term: str) -> None:
        self.run_async(
            lambda: self._search(term),
            on_success=lambda rows: self.documentsSearched.emit(term, rows),
        )

    def resolve_document(self, document_id: int) -> None:
        """Fetch one document's returnable lines.

        By id, because the picker already holds it. The same use case
        answers by reference for a caller that only has the number the
        customer is holding.
        """
        self.run_async(
            lambda: self._resolve(ReturnableDocumentQuery(document_id=document_id)),
            on_success=self.documentResolved.emit,
        )

    def resolve_reference(self, reference: str) -> None:
        self.run_async(
            lambda: self._resolve(ReturnableDocumentQuery(reference=reference)),
            on_success=self.documentResolved.emit,
        )

    def record_return(self, command) -> None:
        self.run_async(lambda: self._record(command), on_success=self.returnRecorded.emit)

    def _page(self, use_case, term: str, number_of):
        """One page of documents matching what has been typed.

        The picker shows document numbers, so that is all this keeps —
        the whole record is fetched only once one has been chosen.
        """
        start, end = _ALL_TIME
        rows = use_case.execute(
            DocumentPageQuery(search=term, page_size=MATCHES, start=start, end=end)
        ).rows
        return [(number_of(row), row.id) for row in rows]


class SaleReturnsViewModel(ReturnsViewModel):
    def _search(self, term: str) -> list[tuple[str, int]]:
        return self._page(
            self._container.page_sales_use_case(), term, lambda sale: sale.invoice_no
        )

    def _resolve(self, request: ReturnableDocumentQuery) -> ReturnableDocument:
        return self._container.get_returnable_sale_use_case().execute(request)

    def _record(self, command):
        return self._container.record_sale_return_use_case().execute(command)


class PurchaseReturnsViewModel(ReturnsViewModel):
    def _search(self, term: str) -> list[tuple[str, int]]:
        return self._page(
            self._container.page_purchases_use_case(),
            term,
            lambda purchase: purchase.purchase_no,
        )

    def _resolve(self, request: ReturnableDocumentQuery) -> ReturnableDocument:
        return self._container.get_returnable_purchase_use_case().execute(request)

    def _record(self, command):
        return self._container.record_purchase_return_use_case().execute(command)
