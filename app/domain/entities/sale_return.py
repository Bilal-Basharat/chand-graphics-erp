from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.entities.base import AuditEntity
from app.domain.entities.sale_return_item import SaleReturnItem


@dataclass(slots=True, kw_only=True)
class SaleReturn(AuditEntity):
    """Goods off one sale, coming back over the counter.

    A document with lines of its own, like the sale it reverses. A
    customer hands back two things at once as one act — one number, one
    conversation about the refund — and recording that as two returns
    would put the same decision on the ledger twice.

    Each line names the sale line it reverses; that is the whole point of
    the record. Without `SaleReturnItem.sale_item_id` there is nothing to
    say how much *can* come back, and stock could be returned that was
    never sold.

    Two amounts, deliberately separate. `return_amount` is what the goods
    were worth and always reduces the invoice; `refund_amount` is money
    actually handed back and may be anything from nothing — the customer
    takes the value against their next invoice — up to the full value.
    It belongs to the return rather than to its lines: one lot of goods
    going back is one decision about money.
    """

    return_no: str
    sale_id: int
    items: list[SaleReturnItem] = field(default_factory=list)

    refund_amount: Decimal = Decimal("0.00")
    refund_method_id: int | None = None
    """How the refund was handed back. None while nothing was refunded,
    and for the same reasons as `SalePayment.payment_method_id` when it
    was."""

    reason: str | None = None
    note: str | None = None
    returned_at: datetime | None = None

    id: int | None = None

    def __post_init__(self) -> None:
        if not self.return_no.strip():
            raise ValueError("return_no cannot be empty")
        if self.refund_amount < 0:
            raise ValueError("refund_amount cannot be negative")
        if self.refund_amount > self.return_amount:
            raise ValueError("refund_amount cannot exceed the value of the goods returned")
        if self.refund_method_id is not None and self.refund_method_id <= 0:
            raise ValueError("refund_method_id must be valid")

    @property
    def return_amount(self) -> Decimal:
        """What the returned goods were worth on the invoice."""
        return sum((item.total_amount for item in self.items), Decimal("0.00"))
