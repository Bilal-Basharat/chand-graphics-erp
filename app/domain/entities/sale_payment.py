from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from app.domain.entities.base import TimestampEntity


@dataclass(slots=True, kw_only=True)
class SalePayment(TimestampEntity):

    amount: Decimal
    reference_no: str | None = None
    note: str | None = None
    received_at: datetime | None = None

    sale_id: int | None = None
    received_by_user_id: int
    id: int | None = None

    payment_method_id: int | None = None
    """Optional. Nothing recorded means the counter default — see
    `presentation.formatting.payment_method_name`. It also becomes None
    when a method that was named is later deleted, so a payment never
    outlives the ability to describe itself."""

    def __post_init__(self) -> None:

        if self.amount <= 0:
            raise ValueError("amount must be greater than zero")
        if self.payment_method_id is not None and self.payment_method_id <= 0:
            raise ValueError("payment_method_id must be valid")
        if self.received_by_user_id <= 0:
            raise ValueError("received_by_user_id must be valid")