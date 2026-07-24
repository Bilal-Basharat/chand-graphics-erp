from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.entities.sale_item import SaleItem
from app.domain.entities.sale_payment import SalePayment
from app.domain.entities.base import AuditEntity


@dataclass(slots=True)
class Sale(AuditEntity):

    invoice_no: str
    note: str | None = None
    discount_amount: Decimal = Decimal("0.00")
    items: list[SaleItem] = field(default_factory=list)
    payments: list[SalePayment] = field(default_factory=list)
    
    customer_id: int | None = None
    # created_by_user_id: int | None = None

    def __post_init__(self) -> None:
        if not self.invoice_no.strip():
            raise ValueError("invoice_no cannot be empty")
        if self.discount_amount < 0:
            raise ValueError("discount_amount cannot be negative")

    def add_item(self, item: SaleItem) -> None:
        self.items.append(item)

    def add_payment(self, payment: SalePayment) -> None:
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