from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from app.domain.entities.base import TimestampEntity


@dataclass(slots=True,kw_only=True)
class PurchasePayment(TimestampEntity):
    
    amount: Decimal
    reference_no: str | None = None
    note: str | None = None

    paid_at: datetime | None = None

    purchase_id: int | None = None
    paid_by_user_id: int
    payment_method_id: int

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("amount must be greater than zero")
        if self.payment_method_id <= 0:
            raise ValueError("payment_method_id must be valid")
        if self.paid_by_user_id <= 0:
            raise ValueError("paid_by_user_id must be valid")