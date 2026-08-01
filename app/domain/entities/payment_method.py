from dataclasses import dataclass

from app.domain.entities.base import AuditEntity


@dataclass(slots=True)
class PaymentMethod(AuditEntity):

    name: str
    id: int | None = None