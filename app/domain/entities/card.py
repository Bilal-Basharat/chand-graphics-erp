from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from app.domain.entities.base import AuditEntity

@dataclass(slots=True)
class Card(AuditEntity):

    card_number: str
    name: str

    purchase_price: Decimal
    selling_price: Decimal

    current_stock: int = 0
    minimum_stock: int = 0

    cabinet_id: int | None = None
    description: str | None = None

    def __post_init__(self) -> None:

        if not self.card_number.strip():
            raise ValueError("card_number cannot be empty")
        if not self.name.strip():
            raise ValueError("name cannot be empty")
        if self.purchase_price < 0:
            raise ValueError("purchase_price cannot be negative")
        if self.selling_price < 0:
            raise ValueError("selling_price cannot be negative")
        if self.current_stock < 0:
            raise ValueError("current_stock cannot be negative")
        if self.minimum_stock < 0:
            raise ValueError("minimum_stock cannot be negative")


    def receive_stock(self, quantity: int) -> None:

        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        self.current_stock += quantity

    def issue_stock(self, quantity: int) -> None:

        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if quantity > self.current_stock:
            raise ValueError("insufficient stock")
        self.current_stock -= quantity


    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.minimum_stock