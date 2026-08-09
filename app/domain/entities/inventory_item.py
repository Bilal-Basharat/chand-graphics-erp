from __future__ import annotations

from dataclasses import dataclass
from app.domain.entities.base import AuditEntity

@dataclass(slots=True, kw_only=True)
class InventoryItem(AuditEntity):
    """
    Non-card inventory catalog record (paper, ink, etc.).

    Deliberately carries no price — see Card for why: price is only
    meaningful per transaction (PurchaseItem/SaleItem.unit_price), not as
    a single mutable "current price" on the catalog record.
    """

    id: int | None = None
    name: str
    current_stock: int = 0
    minimum_stock: int = 0
    description: str | None = None

    unit: str | None = None
    """What one of these is, in the shop's own words — "sheets", "ml",
    "bottles". A label only: stock is counted in whole units of whatever
    this says, so an item bought by the ream and used by the sheet is
    recorded in sheets. Optional, because an item that is simply counted
    needs no word for it."""

    def __post_init__(self) -> None:

        if not self.name.strip():
            raise ValueError("name cannot be empty")
        if self.unit is not None:
            self.unit = " ".join(self.unit.split()) or None
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