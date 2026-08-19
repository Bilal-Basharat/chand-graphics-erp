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
    id: int | None = None
    customer_id: int | None = None

    returned_amount: Decimal = Decimal("0.00")
    """What the goods returned off this invoice were worth.

    Stored rather than summed from the return rows: `balance_amount` is
    read by every list, ageing report and payment screen in the app, and
    none of them load an invoice's returns.
    """

    refunded_amount: Decimal = Decimal("0.00")
    """Money handed back to the customer against those returns.

    Separate from `returned_amount` because a return need not be refunded
    — the value can sit as credit instead — and the two move the balance
    in opposite directions.
    """

    def __post_init__(self) -> None:
        if not self.invoice_no.strip():
            raise ValueError("invoice_no cannot be empty")
        if self.discount_amount < 0:
            raise ValueError("discount_amount cannot be negative")
        if self.returned_amount < 0:
            raise ValueError("returned_amount cannot be negative")
        if self.refunded_amount < 0:
            raise ValueError("refunded_amount cannot be negative")

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
    def net_total(self) -> Decimal:
        """What the invoice is worth now, after anything that came back.

        `grand_total` deliberately keeps its original meaning — what was
        invoiced on the day — so no report quietly changes definition.
        """
        return self.grand_total - self.returned_amount

    @property
    def balance_amount(self) -> Decimal:
        """What the customer still owes.

        A refund is money that left again, so it is added back to what is
        outstanding. Refund nothing against a return and this goes
        negative, which is correct: the customer is in credit.
        """
        return self.net_total - (self.paid_amount - self.refunded_amount)

    @property
    def has_returns(self) -> bool:
        return self.returned_amount > 0