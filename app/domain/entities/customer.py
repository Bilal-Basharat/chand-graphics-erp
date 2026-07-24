from dataclasses import dataclass
from app.domain.entities.base import AuditEntity


@dataclass(slots=True)
class Customer(AuditEntity):

    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    id: int | None = None