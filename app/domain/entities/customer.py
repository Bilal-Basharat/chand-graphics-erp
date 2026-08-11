from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.base import AuditEntity


@dataclass(slots=True)
class Customer(AuditEntity):

    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    opening_balance: Decimal = Decimal("0.00")
    """What this customer already owed before the software was installed.

    Negative is allowed and means the opposite: they are in credit, having
    paid for something not yet invoiced. It is the ledger's starting point
    and is never changed by a sale or a payment — only by editing the
    customer.
    """
    id: int | None = None