from dataclasses import dataclass

from app.domain.entities.base import TimestampEntity


@dataclass(slots=True)
class ExpenseCategory(TimestampEntity):

    name: str
    description: str | None = None
    id: int | None = None
    expense_id: int | None = None