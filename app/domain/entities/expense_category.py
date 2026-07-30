from dataclasses import dataclass

from app.domain.entities.base import AuditEntity


@dataclass(slots=True)
class ExpenseCategory(AuditEntity):

    name: str
    description: str | None = None
    id: int | None = None