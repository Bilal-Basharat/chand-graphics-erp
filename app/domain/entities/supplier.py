from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.base import AuditEntity


@dataclass(slots=True)
class Supplier(AuditEntity):

    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    opening_balance: Decimal = Decimal("0.00")
    """What was already owed to this supplier before the software was
    installed. Negative means the opposite: they hold an advance of yours."""
    id: int | None = None