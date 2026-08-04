from __future__ import annotations

from dataclasses import dataclass
from app.domain.entities.base import AuditEntity

@dataclass(slots=True, kw_only=True)
class Card(AuditEntity):
    """
    Wedding card catalog record.

    Deliberately carries no price: purchase/selling price is only
    meaningful per transaction (PurchaseItem.unit_price /
    SaleItem.unit_price), since the same card is bought and sold at
    different prices over time. A single "current price" field here would
    silently overwrite that history every time a new price was recorded.
    """

    card_number: str
    name: str | None = None

    current_stock: int = 0
    minimum_stock: int = 0

    cabinet_id: int | None = None
    description: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:

        if not self.card_number.strip():
            raise ValueError("card_number cannot be empty")
        if self.name is not None and not self.name.strip():
            raise ValueError("name cannot be blank if provided")
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