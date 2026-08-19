from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.entities.base import AuditEntity
from app.domain.entities.purchase_return_item import PurchaseReturnItem


@dataclass(slots=True, kw_only=True)
class PurchaseReturn(AuditEntity):
    """Goods off one purchase, going back to the supplier.

    The mirror of `SaleReturn`: a document with lines of its own, each
    naming the purchase line it reverses, so no more can go back than
    that bill actually bought.

    Here `refund_amount` is money the supplier gave back rather than
    money handed over the counter; left at nothing, the value stands as
    credit against what is still owed to them.
    """

    return_no: str
    purchase_id: int
    items: list[PurchaseReturnItem] = field(default_factory=list)

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
        """What the returned goods were worth on the bill."""
        return sum((item.total_amount for item in self.items), Decimal("0.00"))
