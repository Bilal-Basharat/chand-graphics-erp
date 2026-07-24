from dataclasses import dataclass

from app.domain.entities.base import TimestampEntity


@dataclass(slots=True)
class PaymentMethod(TimestampEntity):

    name: str
    id: int | None = None