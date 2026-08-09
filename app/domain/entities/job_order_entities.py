"""
The job order aggregate: what the shop was asked to make, what it made it
out of, and what it was paid for it.

A job is the third transaction beside a sale and a purchase, and it is the
one that runs in both directions at once. A purchase brings stock in; a
sale sends stock out and bills for it; a job *consumes* stock to produce
something that was never in stock — ten bill books, five hundred
letterheads — and bills for that instead.

That shape is why the money on a job has two sides, and why they must not
be confused:

    what the customer pays   quantity x unit price, per item, less discount
    what it cost the shop    the materials it ate, plus labour
    profit                   the first minus the second

Labour belongs to the second. The 150 rupees a bill book is sold for
already covers the printing and the binding; charging those to the
customer a second time would inflate the invoice and hide the margin. The
labour lines are here so the shop can see what the job really cost it.

Kept in one module because it is one aggregate: a job item has no meaning
away from its job, and a material line none away from its item. The two
catalogues these point at — product types and labour charge types — are
independent master data and live in their own modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.domain.entities.base import AuditEntity, TimestampEntity
from app.domain.enums.item_type import ItemType
from app.domain.enums.job_status import JobStatus

ZERO = Decimal("0.00")


@dataclass(slots=True, kw_only=True)
class JobMaterial(TimestampEntity):
    """One stock item a job item consumed, and what it cost at the time.

    Points at a card or an inventory item the same way a sale line does,
    so the same stock is spoken about in one language across the app.

    `unit_cost` is copied from the last price the shop paid for it and then
    frozen. A later purchase at a higher price must not rewrite what this
    job cost — that would silently move the profit on work already done.
    """

    item_type: ItemType
    quantity: int
    unit_cost: Decimal

    card_id: int | None = None
    inventory_item_id: int | None = None

    job_item_id: int | None = None
    note: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_cost < 0:
            raise ValueError("unit_cost cannot be negative")

        if self.item_type == ItemType.CARD:
            if self.card_id is None:
                raise ValueError("card_id is required for CARD materials")
            if self.inventory_item_id is not None:
                raise ValueError("inventory_item_id must be None for CARD materials")
        else:
            if self.inventory_item_id is None:
                raise ValueError("inventory_item_id is required for INVENTORY_ITEM materials")
            if self.card_id is not None:
                raise ValueError("card_id must be None for INVENTORY_ITEM materials")

    @property
    def total_cost(self) -> Decimal:
        return self.unit_cost * Decimal(self.quantity)


@dataclass(slots=True, kw_only=True)
class JobLabourCharge(TimestampEntity):
    """What one kind of work on this item cost — printing, binding, cutting.

    Names the type it is rather than carrying the word itself, so renaming
    "Binding" in the catalogue renames it everywhere it has been charged.
    """

    labour_charge_type_id: int
    amount: Decimal

    job_item_id: int | None = None
    note: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("labour charge amount cannot be negative")


@dataclass(slots=True, kw_only=True)
class JobItem(TimestampEntity):
    """One thing the shop was asked to make, and what making it took."""

    product_type_id: int
    quantity: int
    unit_price: Decimal

    specifications: str | None = None
    materials: list[JobMaterial] = field(default_factory=list)
    labour_charges: list[JobLabourCharge] = field(default_factory=list)

    job_id: int | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_price < 0:
            raise ValueError("unit_price cannot be negative")

    def add_material(self, material: JobMaterial) -> None:
        self.materials.append(material)

    def add_labour_charge(self, charge: JobLabourCharge) -> None:
        self.labour_charges.append(charge)

    # ---------------- what the customer pays ----------------

    @property
    def total_amount(self) -> Decimal:
        return self.unit_price * Decimal(self.quantity)

    # ---------------- what it cost the shop ----------------

    @property
    def material_cost(self) -> Decimal:
        return sum((m.total_cost for m in self.materials), ZERO)

    @property
    def labour_cost(self) -> Decimal:
        return sum((c.amount for c in self.labour_charges), ZERO)

    @property
    def cost(self) -> Decimal:
        return self.material_cost + self.labour_cost

    @property
    def profit(self) -> Decimal:
        return self.total_amount - self.cost


@dataclass(slots=True, kw_only=True)
class JobPayment(TimestampEntity):
    amount: Decimal
    """Positive is money taken. Negative is a refund — the reversal written
    when a cancelled job's money goes back.

    A refund is a second row rather than the first one being deleted or
    edited down, so what was collected and what was handed back are both
    on the record. Summed, they leave the job paid nothing, which is the
    truth about a job that never happened."""

    received_by_user_id: int | None = None

    payment_method_id: int | None = None
    """Optional, like a sale payment: nothing chosen means cash."""

    reference_no: str | None = None
    note: str | None = None
    job_id: int | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.amount == ZERO:
            raise ValueError("amount cannot be zero")
        if self.payment_method_id is not None and self.payment_method_id <= 0:
            raise ValueError("payment_method_id must be valid")

    @property
    def is_refund(self) -> bool:
        return self.amount < ZERO


@dataclass(slots=True, kw_only=True)
class Job(AuditEntity):
    job_no: str
    customer_id: int | None = None
    status: JobStatus = JobStatus.DRAFT
    """How far the work has got: draft, in production, completed,
    delivered — moved on one step at a time from the job list.

    A job starts as a draft: written down and costed, but not yet on the
    press. Its materials leave stock at that point rather than when
    production starts, because they are committed to this job from the
    moment it is written down. Cancelling puts them back."""

    promised_date: date | None = None
    discount_amount: Decimal = ZERO
    completed_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    note: str | None = None

    items: list[JobItem] = field(default_factory=list)
    payments: list[JobPayment] = field(default_factory=list)
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.job_no.strip():
            raise ValueError("job_no cannot be empty")
        if self.discount_amount < 0:
            raise ValueError("discount_amount cannot be negative")

    def add_item(self, item: JobItem) -> None:
        self.items.append(item)

    def add_payment(self, payment: JobPayment) -> None:
        self.payments.append(payment)

    @property
    def is_void(self) -> bool:
        """Whether this job charged nothing and cost nothing.

        A cancelled one did. Its materials went back to stock and any
        money taken was refunded, both as reversing records rather than
        by deleting anything — so the items and the payments stay, as the
        record of what was attempted, while the figures below answer
        zero. Every screen that adds jobs up therefore gets a cancelled
        one right without knowing what cancelling means.
        """
        return self.status is JobStatus.CANCELLED

    # ---------------- what the customer pays ----------------

    @property
    def subtotal(self) -> Decimal:
        """What the lines come to. Unaffected by cancelling: the work was
        quoted at this, whatever became of it."""
        return sum((i.total_amount for i in self.items), ZERO)

    @property
    def grand_total(self) -> Decimal:
        if self.is_void:
            return ZERO
        total = self.subtotal - self.discount_amount
        if total < 0:
            raise ValueError("discount_amount cannot exceed subtotal")
        return total

    @property
    def paid_amount(self) -> Decimal:
        return sum((p.amount for p in self.payments), ZERO)

    @property
    def balance_amount(self) -> Decimal:
        return self.grand_total - self.paid_amount

    # ---------------- what it cost the shop ----------------

    @property
    def material_cost(self) -> Decimal:
        return sum((i.material_cost for i in self.items), ZERO)

    @property
    def labour_cost(self) -> Decimal:
        return sum((i.labour_cost for i in self.items), ZERO)

    @property
    def cost(self) -> Decimal:
        return ZERO if self.is_void else self.material_cost + self.labour_cost

    @property
    def profit(self) -> Decimal:
        """Positive is a profit, negative a loss. Measured against the
        discounted total, because that is what was actually charged.

        Zero on a cancelled job — nothing charged less nothing spent.
        """
        return self.grand_total - self.cost
