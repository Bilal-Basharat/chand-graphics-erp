from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.entities.purchase_item import PurchaseItem
from app.domain.entities.purchase_payment import PurchasePayment
from app.domain.entities.base import AuditEntity

@dataclass(slots=True)
class Purchase(AuditEntity):

    purchase_no: str
    note: str | None = None
    discount_amount: Decimal = Decimal("0.00")
    items: list[PurchaseItem] = field(default_factory=list)
    payments: list[PurchasePayment] = field(default_factory=list)
    reference_no: str | None = None
    
    # created_by_user_id: int | None = None
    supplier_id: int | None = None


    def __post_init__(self) -> None:

        if not self.purchase_no.strip():
            raise ValueError("purchase_no cannot be empty")
        if self.discount_amount < 0:
            raise ValueError("discount_amount cannot be negative")


    def add_item(self, item: PurchaseItem) -> None:
        self.items.append(item)


    def add_payment(self, payment: PurchasePayment) -> None:
        self.payments.append(payment)


    @property
    def subtotal(self) -> Decimal:
        return sum((item.total_amount for item in self.items), Decimal("0.00"))


    @property
    def grand_total(self) -> Decimal:
        total = self.subtotal - self.discount_amount

        if total < 0:
            raise ValueError("discount_amount cannot exceed subtotal")
        return total


    @property
    def paid_amount(self) -> Decimal:
        return sum((payment.amount for payment in self.payments), Decimal("0.00"))


    @property
    def balance_amount(self) -> Decimal:
        return self.grand_total - self.paid_amount