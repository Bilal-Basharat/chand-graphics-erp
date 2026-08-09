"""
Recording and reading job orders.

Creating a job is the only write in this application that both consumes
stock and bills for something that was never in stock. Both halves happen
in one unit of work: if a single material is short, nothing is deducted
and no job is recorded, because a job whose materials were only half
taken would leave the stock figures lying.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.auth.session import CurrentUserSession
from app.application.dto.commands import (
    CancelJobCommand,
    CreateJobCommand,
    DateRangeQuery,
    JobItemCommand,
    JobMaterialCommand,
    RecordJobPaymentCommand,
    UpdateJobStatusCommand,
)
from app.application.dto.queries import SearchQuery
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import AuthorizedUnitOfWorkUseCase
from app.application.use_cases.stock_helpers import (
    ResolvedStockTarget,
    decrease_stock,
    increase_stock,
    load_stock_target,
)
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.entities.job_order_entities import (
    Job,
    JobItem,
    JobLabourCharge,
    JobMaterial,
    JobPayment,
)
from app.domain.enums.item_type import ItemType
from app.domain.enums.job_status import CANCELLABLE, JobStatus
from app.domain.enums.movement_type import MovementType
from app.shared.datetimes import now_pkt

SOURCE_DOCUMENT_TYPE = "JOB"

_ZERO = Decimal("0.00")


def _material_key(material: JobMaterialCommand | JobMaterial) -> tuple[str, int]:
    """Which stock item a material line points at.

    Takes the command on the way in and the entity on the way back out —
    both name their target the same way, and consuming and returning have
    to agree on what "the same paper" means or a cancellation would
    credit the wrong shelf.
    """
    if material.item_type == ItemType.CARD:
        if material.card_id is None:
            raise ValueError("card_id is required for CARD materials")
        return ("CARD", material.card_id)
    if material.inventory_item_id is None:
        raise ValueError("inventory_item_id is required for INVENTORY_ITEM materials")
    return ("ITEM", material.inventory_item_id)


class CreateJobUseCase(AuthorizedUnitOfWorkUseCase[CreateJobCommand, Job]):
    def execute(self, request: CreateJobCommand) -> Job:
        self.require_permission(Permission.MANAGE_JOBS)

        if not request.items:
            raise ValueError("job must contain at least one item")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            jobs = self.require(uow.jobs, "jobs")
            customers = self.require(uow.customers, "customers")
            product_types = self.require(uow.product_types, "product_types")
            labour_charge_types = self.require(uow.labour_charge_types, "labour_charge_types")
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            purchases = self.require(uow.purchases, "purchases")
            movements = self.require(uow.inventory_movements, "inventory_movements")
            users = self.require(uow.users, "users")

            if request.customer_id is not None and customers.get_by_id(request.customer_id) is None:
                raise NotFoundError(f"Customer id={request.customer_id} not found")

            # Checked here rather than left to the unique index — see
            # CreateSaleUseCase for why a colliding number deserves an
            # ordinary message rather than a driver error.
            job_no = request.job_no.strip()
            if jobs.get_by_job_no(job_no) is not None:
                raise DuplicateEntityError(f"Job '{job_no}' already exists.")

            job = Job(
                job_no=job_no,
                customer_id=request.customer_id,
                promised_date=request.promised_date,
                note=request.note,
                discount_amount=request.discount_amount,
                created_by_user_id=current_user_id,
            )
            # Status is left at the entity's own default — one place
            # decides what a job starts as.

            # One target per stock item across the whole job, so two items
            # drawing on the same paper are checked against one running
            # figure rather than each against the opening one.
            stock_cache: dict[tuple[str, int], ResolvedStockTarget] = {}
            consumed: list[tuple[JobMaterial, int, int]] = []

            for item_command in request.items:
                job.add_item(
                    self._build_item(
                        item_command,
                        product_types=product_types,
                        labour_charge_types=labour_charge_types,
                        purchases=purchases,
                        uow=uow,
                        stock_cache=stock_cache,
                        consumed=consumed,
                    )
                )

            for target in stock_cache.values():
                target.repository.update(target.entity)

            for payment in request.payments:
                if (
                    payment.payment_method_id is not None
                    and payment_methods.get_by_id(payment.payment_method_id) is None
                ):
                    raise NotFoundError(f"Payment method id={payment.payment_method_id} not found")
                if users.get_by_id(payment.received_by_user_id) is None:
                    raise NotFoundError(f"User id={payment.received_by_user_id} not found")

                job.add_payment(
                    JobPayment(
                        amount=payment.amount,
                        payment_method_id=payment.payment_method_id,
                        received_by_user_id=payment.received_by_user_id,
                        reference_no=payment.reference_no,
                        note=payment.note,
                    )
                )

            if job.paid_amount > job.grand_total:
                raise ValueError("paid amount cannot exceed grand total")

            saved = jobs.add(job)

            # Written after the job has an id, so every movement can name
            # the document that caused it.
            occurred_at = now_pkt()
            for material, previous_stock, resulting_stock in consumed:
                movements.add(
                    InventoryMovement(
                        movement_type=MovementType.CONSUMPTION,
                        item_type=material.item_type,
                        quantity=material.quantity,
                        card_id=material.card_id,
                        inventory_item_id=material.inventory_item_id,
                        unit_price=material.unit_cost,
                        previous_stock=previous_stock,
                        resulting_stock=resulting_stock,
                        source_document_type=SOURCE_DOCUMENT_TYPE,
                        source_document_id=saved.id,
                        reference_no=saved.job_no,
                        occurred_at=occurred_at,
                        created_by_user_id=current_user_id,
                    )
                )

            return saved

    def _build_item(
        self,
        command: JobItemCommand,
        *,
        product_types,
        labour_charge_types,
        purchases,
        uow,
        stock_cache: dict[tuple[str, int], ResolvedStockTarget],
        consumed: list[tuple[JobMaterial, int, int]],
    ) -> JobItem:
        if product_types.get_by_id(command.product_type_id) is None:
            raise NotFoundError(f"Product type id={command.product_type_id} not found")

        item = JobItem(
            product_type_id=command.product_type_id,
            quantity=command.quantity,
            unit_price=command.unit_price,
            specifications=command.specifications,
        )

        for material_command in command.materials:
            key = _material_key(material_command)
            if key not in stock_cache:
                stock_cache[key] = load_stock_target(
                    uow=uow,
                    item_type=material_command.item_type,
                    card_id=material_command.card_id,
                    inventory_item_id=material_command.inventory_item_id,
                )
            entity = stock_cache[key].entity

            # `issue_stock` refuses to go negative, but its message says
            # only "insufficient stock". Named here, because the user needs
            # to know which of five materials ran out.
            if material_command.quantity > entity.current_stock:
                raise ValueError(
                    f"Only {entity.current_stock} of "
                    f"'{_describe(entity)}' in stock; the job needs "
                    f"{material_command.quantity}."
                )

            previous_stock, resulting_stock = decrease_stock(entity, material_command.quantity)

            unit_cost = material_command.unit_cost
            if unit_cost is None:
                unit_cost = purchases.latest_unit_price(
                    material_command.item_type,
                    material_command.card_id or material_command.inventory_item_id,
                )
            material = JobMaterial(
                item_type=material_command.item_type,
                quantity=material_command.quantity,
                unit_cost=unit_cost if unit_cost is not None else _ZERO,
                card_id=material_command.card_id,
                inventory_item_id=material_command.inventory_item_id,
                note=material_command.note,
            )
            item.add_material(material)
            consumed.append((material, previous_stock, resulting_stock))

        for charge_command in command.labour_charges:
            if labour_charge_types.get_by_id(charge_command.labour_charge_type_id) is None:
                raise NotFoundError(
                    f"Labour charge type id={charge_command.labour_charge_type_id} not found"
                )
            item.add_labour_charge(
                JobLabourCharge(
                    labour_charge_type_id=charge_command.labour_charge_type_id,
                    amount=charge_command.amount,
                    note=charge_command.note,
                )
            )

        return item


class RecordJobPaymentUseCase(AuthorizedUnitOfWorkUseCase[RecordJobPaymentCommand, Job]):
    """Collect against a job that was recorded unpaid or part paid."""

    def execute(self, request: RecordJobPaymentCommand) -> Job:
        self.require_permission(Permission.MANAGE_JOBS)

        with self.uow as uow:
            jobs = self.require(uow.jobs, "jobs")
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            users = self.require(uow.users, "users")

            job = jobs.get_by_id(request.job_id)
            if job is None:
                raise NotFoundError(f"Job id={request.job_id} not found")

            if (
                request.payment_method_id is not None
                and payment_methods.get_by_id(request.payment_method_id) is None
            ):
                raise NotFoundError(f"Payment method id={request.payment_method_id} not found")

            if users.get_by_id(request.received_by_user_id) is None:
                raise NotFoundError(f"User id={request.received_by_user_id} not found")

            if request.amount > job.balance_amount:
                raise ValueError("payment amount cannot exceed outstanding balance")

            job.add_payment(
                JobPayment(
                    amount=request.amount,
                    payment_method_id=request.payment_method_id,
                    received_by_user_id=request.received_by_user_id,
                    reference_no=request.reference_no,
                    note=request.note,
                )
            )

            return jobs.update(job)


class UpdateJobStatusUseCase(AuthorizedUnitOfWorkUseCase[UpdateJobStatusCommand, Job]):
    """Move a job along: in production, completed, delivered.

    Stamps the matching date as it goes, so "when was this finished" is
    answerable without reading an audit trail.

    Cancelling is not one of these. It undoes the job rather than
    recording where it got to, so it belongs to `CancelJobUseCase` — and
    is refused here, or a job's materials would stay gone and its money
    unreturned while the list said otherwise.
    """

    def execute(self, request: UpdateJobStatusCommand) -> Job:
        self.require_permission(Permission.MANAGE_JOBS)

        if request.status is JobStatus.CANCELLED:
            raise ValueError("Cancelling a job goes through CancelJobUseCase.")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            jobs = self.require(uow.jobs, "jobs")

            job = jobs.get_by_id(request.job_id)
            if job is None:
                raise NotFoundError(f"Job id={request.job_id} not found")
            if job.status is JobStatus.CANCELLED:
                raise ValueError(f"Job '{job.job_no}' was cancelled and cannot be moved on.")

            now = now_pkt()
            job.status = request.status
            if request.status is JobStatus.COMPLETED and job.completed_at is None:
                job.completed_at = now
            if request.status is JobStatus.DELIVERED:
                job.completed_at = job.completed_at or now
                job.delivered_at = now
            job.updated_by_user_id = current_user_id

            return jobs.update(job)


class CancelJobUseCase(AuthorizedUnitOfWorkUseCase[CancelJobCommand, Job]):
    """Call a job off: materials back to stock, money back to the customer.

    Both halves are written as reversing records rather than by deleting
    anything. The job keeps its items and its payments — what was ordered
    and what was collected are part of the shop's history whether or not
    the work happened — and `Job.is_void` is what makes its totals read
    zero from then on.

    The stock half goes into the movement ledger as RETURN rows against
    this job, answering the CONSUMPTION rows it wrote when it was
    recorded. An item's history then reads "taken for JOB-x, put back for
    JOB-x" instead of five hundred sheets vanishing and reappearing with
    nothing to connect them.

    Those movements are written here, inside the job's own unit of work,
    rather than by calling `RecordInventoryMovementUseCase`: that use case
    opens a transaction of its own per movement, so a cancellation that
    failed halfway would leave stock the ledger cannot account for. One
    unit of work is the same guarantee `CreateJobUseCase` relies on.
    """

    def execute(self, request: CancelJobCommand) -> Job:
        self.require_permission(Permission.MANAGE_JOBS)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            jobs = self.require(uow.jobs, "jobs")
            movements = self.require(uow.inventory_movements, "inventory_movements")

            job = jobs.get_by_id(request.job_id)
            if job is None:
                raise NotFoundError(f"Job id={request.job_id} not found")
            if job.status is JobStatus.CANCELLED:
                raise ValueError(f"Job '{job.job_no}' is already cancelled.")
            if job.status not in CANCELLABLE:
                raise ValueError(
                    f"Job '{job.job_no}' is {job.status.value.replace('_', ' ').lower()}. "
                    "Its materials are already spent — record a stock return or a "
                    "write-off instead of cancelling."
                )

            reason = (request.reason or "").strip() or f"Job {job.job_no} cancelled"
            now = now_pkt()

            self._return_materials(
                job,
                uow=uow,
                movements=movements,
                reason=reason,
                occurred_at=now,
                current_user_id=current_user_id,
            )
            self._refund_payments(job, reason=reason, current_user_id=current_user_id)

            job.status = JobStatus.CANCELLED
            job.cancelled_at = now
            job.updated_by_user_id = current_user_id

            return jobs.update(job)

    def _return_materials(
        self,
        job: Job,
        *,
        uow,
        movements,
        reason: str,
        occurred_at: datetime,
        current_user_id: int | None,
    ) -> None:
        """Put every material back, one running figure per stock item.

        Cached the same way the job consumed them, so two items that both
        ate the same paper return against one count rather than each
        against a stale opening figure.
        """
        stock_cache: dict[tuple[str, int], ResolvedStockTarget] = {}

        for item in job.items:
            for material in item.materials:
                key = _material_key(material)
                if key not in stock_cache:
                    stock_cache[key] = load_stock_target(
                        uow=uow,
                        item_type=material.item_type,
                        card_id=material.card_id,
                        inventory_item_id=material.inventory_item_id,
                    )
                previous_stock, resulting_stock = increase_stock(
                    stock_cache[key].entity, material.quantity
                )
                movements.add(
                    InventoryMovement(
                        movement_type=MovementType.RETURN,
                        item_type=material.item_type,
                        quantity=material.quantity,
                        card_id=material.card_id,
                        inventory_item_id=material.inventory_item_id,
                        unit_price=material.unit_cost,
                        previous_stock=previous_stock,
                        resulting_stock=resulting_stock,
                        source_document_type=SOURCE_DOCUMENT_TYPE,
                        source_document_id=job.id,
                        reference_no=job.job_no,
                        reason=reason,
                        occurred_at=occurred_at,
                        created_by_user_id=current_user_id,
                    )
                )

        for target in stock_cache.values():
            target.repository.update(target.entity)

    @staticmethod
    def _refund_payments(job: Job, *, reason: str, current_user_id: int | None) -> None:
        """Reverse each instalment separately, keeping its method.

        One row per payment rather than a single row for the net, because
        money goes back the way it came: cash as cash, a transfer as a
        transfer, and the person handing it over needs to know which.
        """
        for payment in list(job.payments):
            if payment.is_refund:
                continue
            job.add_payment(
                JobPayment(
                    amount=-payment.amount,
                    payment_method_id=payment.payment_method_id,
                    received_by_user_id=current_user_id,
                    reference_no=payment.reference_no,
                    note=f"Refund — {reason}",
                )
            )


class GetJobByJobNoUseCase(AuthenticatedUseCase[str, Job | None]):
    def __init__(self, uow, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> Job | None:
        with self.uow as uow:
            return self.require(uow.jobs, "jobs").get_by_job_no(request.strip())


class ListJobsByDateRangeUseCase(AuthenticatedUseCase[DateRangeQuery, list[Job]]):
    def __init__(self, uow, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: DateRangeQuery) -> list[Job]:
        with self.uow as uow:
            jobs = self.require(uow.jobs, "jobs")
            return jobs.list_by_date_range(request.start, request.end, request.limit)


class SearchJobsUseCase(AuthenticatedUseCase[SearchQuery, list[Job]]):
    def __init__(self, uow, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: SearchQuery) -> list[Job]:
        with self.uow as uow:
            jobs = self.require(uow.jobs, "jobs")
            return jobs.search_by_term(request.term, request.limit)


class GetMaterialUnitCostUseCase(AuthenticatedUseCase[tuple[ItemType, int], Decimal | None]):
    """What one of a stock item last cost, for the material form to offer.

    None means it has never been purchased, which the form reports rather
    than quietly costing the job at zero.
    """

    def __init__(self, uow, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: tuple[ItemType, int]) -> Decimal | None:
        item_type, item_id = request
        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            return purchases.latest_unit_price(item_type, item_id)


def _describe(entity) -> str:
    return getattr(entity, "name", None) or getattr(entity, "card_number", "item")
