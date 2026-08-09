"""
View model for the job orders screen: the period-filtered job list, the
catalogues the new-job builder picks from, and recording a job.

Mirrors `SalesViewModel` — listing is by date range and the create dialog
needs several catalogues, so neither fits `CollectionSource` and both
implement the collection contract directly.
"""
from __future__ import annotations

from PySide6.QtCore import Signal

from app.application.dto.commands import (
    CancelJobCommand,
    CreateJobCommand,
    UpdateJobStatusCommand,
)
from app.application.dto.queries import SearchQuery
from app.container import AppContainer
from app.domain.enums.item_type import ItemType
from app.domain.enums.job_status import JobStatus
from app.presentation.formatting import DASH, WALK_IN, payment_method_name
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.viewmodels.document_items import PaymentLine, payment_lines
from app.presentation.viewmodels.job_items import JobCatalogue, JobItemLine
from app.presentation.widgets.period_selector import PeriodSelection

_REFERENCE_LIMIT = 500
_SEARCH_LIMIT = 200


class JobsViewModel(CollectionViewModelBase):
    referenceLoaded = Signal(dict)
    statusChanged = Signal(object)

    def __init__(self, container: AppContainer, period: PeriodSelection) -> None:
        super().__init__()
        self._container = container
        self._period = period
        self._customer_names: dict[int, str] = {}
        self._method_names: dict[int, str] = {}
        self._catalogue = JobCatalogue()

    # ---------------- listing ----------------

    def load(self) -> None:
        use_case = self._container.list_jobs_by_date_range_use_case()
        self.run_async(
            lambda: use_case.execute(self._period.as_query()),
            on_success=self.rowsLoaded.emit,
        )

    def search(self, term: str) -> None:
        term = term.strip()
        if not term:
            self.load()
            return
        use_case = self._container.search_jobs_use_case()
        self.run_async(
            lambda: use_case.execute(SearchQuery(term=term, limit=_SEARCH_LIMIT)),
            on_success=self.rowsLoaded.emit,
        )

    # ---------------- naming ----------------

    def customer_name(self, job) -> str:
        if not job.customer_id:
            return WALK_IN
        return self._customer_names.get(job.customer_id, DASH)

    def item_lines(self, job) -> list[JobItemLine]:
        """What a job made, ready to read underneath it."""
        return self._catalogue.lines_of(job)

    def payment_lines(self, job) -> list[PaymentLine]:
        """What has been paid against one job, oldest first. A cancelled
        job's refund is in here too, as the negative payment it is."""
        return payment_lines(
            job,
            dated=lambda payment: payment.created_at,
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
                "product_types": self._container.list_product_types_use_case().execute(
                    _REFERENCE_LIMIT
                ),
                "labour_charge_types": self._container.list_labour_charge_types_use_case().execute(
                    _REFERENCE_LIMIT
                ),
                "cards": self._container.list_cards_use_case().execute(_REFERENCE_LIMIT),
                "inventory_items": self._container.list_inventory_items_use_case().execute(
                    _REFERENCE_LIMIT
                ),
            }

        def _on_success(reference: dict) -> None:
            self._customer_names = {c.id: c.name for c in reference["customers"]}
            self._method_names = {m.id: m.name for m in reference["payment_methods"]}
            self._catalogue.set_reference(
                product_types=reference["product_types"],
                labour_charge_types=reference["labour_charge_types"],
                cards=reference["cards"],
                inventory_items=reference["inventory_items"],
            )
            self.referenceLoaded.emit(reference)

        self.run_async(fetch, on_success=_on_success)

    def material_unit_cost(self, item_type: ItemType, item_id: int, on_success) -> None:
        """The last price paid for a stock item, for the material form."""
        use_case = self._container.get_material_unit_cost_use_case()
        self.run_async(lambda: use_case.execute((item_type, item_id)), on_success=on_success)

    # ---------------- writing ----------------

    def create(self, command: CreateJobCommand) -> None:
        use_case = self._container.create_job_use_case()

        def _on_success(job) -> None:
            self.itemCreated.emit(job)
            self.load()
            # Materials were consumed, so the dialog's catalogues are stale.
            self.load_reference_data()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)

    def set_status(self, job_id: int, status: JobStatus) -> None:
        use_case = self._container.update_job_status_use_case()

        def _on_success(job) -> None:
            self.statusChanged.emit(job)
            self.load()

        self.run_async(
            lambda: use_case.execute(UpdateJobStatusCommand(job_id=job_id, status=status)),
            on_success=_on_success,
        )

    def cancel(self, job_id: int, reason: str | None = None) -> None:
        """Call a job off. Its own use case, not a status move — see
        `CancelJobUseCase`: this returns the materials to stock and the
        money to the customer."""
        use_case = self._container.cancel_job_use_case()

        def _on_success(job) -> None:
            self.statusChanged.emit(job)
            self.load()
            # Stock came back, so the create dialog's figures are stale.
            self.load_reference_data()

        self.run_async(
            lambda: use_case.execute(CancelJobCommand(job_id=job_id, reason=reason)),
            on_success=_on_success,
        )
