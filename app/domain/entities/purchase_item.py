from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.domain.entities.base import TimestampEntity


@dataclass(slots=True, kw_only=True)
class PurchaseItem(TimestampEntity):

    item_type: ItemType
    quantity: int
    unit_price: Decimal

    card_id: int | None = None
    inventory_item_id: int | None = None
    purchase_id: int | None = None

    previous_stock: int | None = None
    resulting_stock: int | None = None

    note: str | None = None
    
    def __post_init__(self) -> None:

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_price < 0:
            raise ValueError("unit_price cannot be negative")

        if self.item_type == ItemType.CARD:
            if self.card_id is None:
                raise ValueError("card_id is required for CARD items")
            if self.inventory_item_id is not None:
                raise ValueError("inventory_item_id must be None for CARD items")

        if self.item_type == ItemType.INVENTORY_ITEM:
            if self.inventory_item_id is None:
                raise ValueError("inventory_item_id is required for INVENTORY_ITEM items")
            if self.card_id is not None:
                raise ValueError("card_id must be None for INVENTORY_ITEM items")

    @property

    def total_amount(self) -> Decimal:
        return self.unit_price * Decimal(self.quantity)