"""
Job orders: what the shop has been asked to make, what it charged, what
it cost, and whether it made money.

Read alongside `sales_view.py` — a job is the same list screen with one
extra question. A sale does not know what it cost the shop; a job does,
because the job records what went into it. So this screen shows COSTS
where sales shows discount, and each job opens to reveal the items behind
that figure.
"""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QWidget

from app.domain.enums.job_status import CANCELLABLE, JobStatus
from app.presentation.dialogs.confirm import confirm_destructive
from app.presentation.dialogs.new_job_dialog import NewJobDialog
from app.presentation.formatting import date_time, money
from app.presentation.records.builders import job_card
from app.presentation.records.card import RecordCard
from app.presentation.viewmodels.jobs_viewmodel import JobsViewModel
from app.presentation.views.collection_view import VIEW_ACTION, CollectionPage, CollectionView
from app.presentation.views.document_lists import created_at
from app.presentation.widgets.grouped_table import GroupedTable
from app.presentation.widgets.job_status import job_status as _status
from app.presentation.widgets.job_status import job_status_color, job_status_text
from app.presentation.widgets.list_controls import FilterOption
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.table_model import Column, detail_columns

_ZERO = Decimal("0.00")

# What a job moves to next, and what the button that moves it there says.
# Only forward: a delivered job going back to "in production" would be a
# correction, not a step, and corrections belong with editing rather than
# a row button.
#
# The button names the status it produces rather than saying "Advance",
# because "advance" only tells you something will change — the user is
# left to work out into what, on every row, from the status column beside
# it.
_ADVANCE: dict[JobStatus, tuple[JobStatus, str]] = {
    JobStatus.DRAFT: (JobStatus.IN_PRODUCTION, "Start production"),
    JobStatus.IN_PRODUCTION: (JobStatus.COMPLETED, "Mark completed"),
    JobStatus.COMPLETED: (JobStatus.DELIVERED, "Mark delivered"),
}

_WIDEST_ADVANCE = "Start production"
"""The longest wording above. It sizes the button's slot so the column
holds still down the list instead of shifting row by row."""

_ADVANCE_KEY = "advance"
_CANCEL_KEY = "cancel"


def _advance_label(job) -> str:
    """What moving this job on would make it. Blank once it is delivered
    or cancelled: there is nowhere left to go, and an empty slot says that
    more plainly than a dead button would."""
    step = _ADVANCE.get(_status(job))
    return step[1] if step is not None else ""


def _cancellable(job) -> bool:
    return _status(job) in CANCELLABLE


class JobsView(CollectionView):
    def __init__(
        self,
        view_model: JobsViewModel,
        period: PeriodSelection,
        current_user_id_provider,
        parent: QWidget | None = None,
    ) -> None:
        self._period = period
        self._jobs_view_model = view_model
        self._current_user_id_provider = current_user_id_provider
        self._reference: dict = {}

        super().__init__(
            CollectionPage(
                crumb=("Operations", "Job orders"),
                title="Job orders",
                subtitle="Work made to order — what it was charged at, and what it cost to make.",
                panel_title="Job list",
                empty_message="No job orders in this period.",
                unit="job",
                search_placeholder="Search by job number or customer",
                create_label="Add job order",
            ),
            [
                # Wide enough for the whole generated number — JOB- plus a
                # timestamp is 16 characters, and a job elided down to
                # "JOB-2608071..." cannot be told from the one beside it.
                Column("JOB #", lambda j: j.job_no, width=185),
                Column("CUSTOMER", view_model.customer_name),
                Column(
                    "STATUS",
                    job_status_text,
                    align="center",
                    color=job_status_color,
                    sort_key=lambda j: str(j.status),
                    width=130,
                ),
                Column(
                    "CHARGED",
                    lambda j: money(j.grand_total),
                    align="right",
                    sort_key=lambda j: j.grand_total,
                    width=130,
                ),
                Column(
                    "COSTS",
                    lambda j: money(j.cost),
                    align="right",
                    sort_key=lambda j: j.cost,
                    width=130,
                ),
                Column("DATE", lambda j: date_time(j.created_at), sort_key=created_at, width=170),
            ],
            view_model,
            parent,
        )

        view_model.referenceLoaded.connect(self._on_reference_loaded)

    # ---------------- shape ----------------

    def create_table(self, columns: Sequence[Column]) -> GroupedTable:
        return GroupedTable(
            columns,
            detail_columns(
                columns,
                # Materials go under the widest column there is: a bill
                # book eats three or four of them, and the list of what it
                # ate is the whole reason to open a job. The rest fall
                # where their parent column puts them — a grouped table
                # shares one grid, so amounts stay under amounts.
                {
                    "JOB #": ("ITEM", lambda line: line.label),
                    "CUSTOMER": ("MATERIALS USED", lambda line: line.materials),
                    "STATUS": ("QUANTITY", lambda line: line.quantity),
                    "COSTS": ("COST", lambda line: money(line.cost)),
                    "CHARGED": ("CHARGED", lambda line: money(line.total)),
                },
            ),
            children_of=self._jobs_view_model.item_lines,
            placeholder="No job orders in this period.",
        )

    def filter_options(self) -> Sequence[FilterOption]:
        return (
            FilterOption("In production", lambda j: _status(j) is JobStatus.IN_PRODUCTION),
            FilterOption("Completed", lambda j: _status(j) is JobStatus.COMPLETED),
            FilterOption("Delivered", lambda j: _status(j) is JobStatus.DELIVERED),
            FilterOption("Cancelled", lambda j: _status(j) is JobStatus.CANCELLED),
            # "Cost more than it charged" rather than "Made a loss": the
            # word margin is gone from this screen, and the two figures the
            # filter compares are both still on the row.
            FilterOption("Cost more than it charged", lambda j: j.cost > j.grand_total),
            FilterOption("Not fully paid", lambda j: j.balance_amount > _ZERO),
        )

    def toolbar_extras(self) -> list[QWidget]:
        selector = PeriodSelector(self._period)
        selector.periodChanged.connect(self.reload)
        return [selector]

    def summary(self, rows: list):
        return (
            ("Charged", money(sum((j.grand_total for j in rows), _ZERO))),
            ("Costs", money(sum((j.cost for j in rows), _ZERO))),
        )

    def row_actions(self) -> Sequence[RowAction]:
        return (
            VIEW_ACTION,
            RowAction(_ADVANCE_KEY, _WIDEST_ADVANCE, label_of=_advance_label),
            RowAction(_CANCEL_KEY, "Cancel", tone="danger", enabled_of=_cancellable),
        )

    def record_card(self, row) -> RecordCard:
        return job_card(
            row,
            customer=self._jobs_view_model.customer_name(row),
            items=self._jobs_view_model.item_lines(row),
            payments=self._jobs_view_model.payment_lines(row),
        )

    # ---------------- behaviour ----------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Refreshed on every visit: stock, customers and both catalogues are
        # edited on other screens, and a dialog offering a stale list of
        # them is worse than a reload.
        self._jobs_view_model.load_reference_data()

    def _on_reference_loaded(self, reference: dict) -> None:
        self._reference = reference
        # Product and material names arrive after the rows that show them.
        self.table.refresh()

    def open_create_dialog(self) -> None:
        if not self._reference:
            self._jobs_view_model.errorOccurred.emit(
                "Still loading products and stock — try again in a moment."
            )
            return
        NewJobDialog(
            self._jobs_view_model,
            customers=self._reference["customers"],
            payment_methods=self._reference["payment_methods"],
            product_types=self._reference["product_types"],
            labour_charge_types=self._reference["labour_charge_types"],
            cards=self._reference["cards"],
            inventory_items=self._reference["inventory_items"],
            current_user_id=self._current_user_id_provider(),
            parent=self,
        ).exec()

    def on_row_action(self, key: str, row) -> None:
        # Neither button reaches here on a row it cannot act on — the
        # delegate greys the one and leaves the other unpainted — so both
        # branches below can assume a move is available.
        if key == _CANCEL_KEY:
            if not confirm_destructive(
                self,
                title="Cancel job",
                message=(
                    f"Cancel {row.job_no}?\n\n"
                    "Its materials go back into stock and anything paid is "
                    "refunded, both recorded so the ledger can be read back.\n\n"
                    "If some of the materials were already used up, record the "
                    "waste on Inventory movement afterwards."
                ),
                confirm_label="Cancel job",
                cancel_label="Keep it",
            ):
                return
            self._jobs_view_model.cancel(row.id)
            return

        step = _ADVANCE.get(_status(row))
        if step is not None:
            self._jobs_view_model.set_status(row.id, step[0])
