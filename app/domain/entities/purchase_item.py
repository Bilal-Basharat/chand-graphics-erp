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

    inventory_item_id: int | None = None
    purchase_id: int | None = None

    previous_stock: int | None = None
    resulting_stock: int | None = None

    note: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_price < 0:
            raise ValueError("unit_price cannot be negative")

        # See SaleItem: the line carries the id its own item type names.
        if self.item_type is ItemType.INVENTORY_ITEM and self.inventory_item_id is None:
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM items")

    @property
    def total_amount(self) -> Decimal:
        return self.unit_price * Decimal(self.quantity)
