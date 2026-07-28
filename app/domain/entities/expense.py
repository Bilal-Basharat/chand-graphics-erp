from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from app.domain.entities.base import AuditEntity

@dataclass(slots=True)
class Expense(AuditEntity):
    
    expense_name: str
    total_amount: Decimal
    quantity: int | None = None
    unit_price: Decimal | None = None
    remarks: str | None = None
    category_id: int | None = None
    id: int | None = None
    
    @property
    def amount(self) -> Decimal:
        return self.total_amount

    def __post_init__(self) -> None:

        if not self.expense_name.strip():
            raise ValueError("expense_name cannot be empty")

        # AUTO-CALCULATE LOGIC
        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_price is not None and self.unit_price < 0:
            raise ValueError("unit_price cannot be negative")

                
        # Auto-calculate if amount is 0
        if self.total_amount == Decimal("0.00") and self.quantity and self.unit_price:
            self.total_amount = self.quantity * self.unit_price

        if self.total_amount <= 0:
            raise ValueError("total_amount must be greater than zero")