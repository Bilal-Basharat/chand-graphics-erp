from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.domain.entities.base import TimestampEntity


@dataclass(slots=True, kw_only=True)
class SaleItem(TimestampEntity):

    item_type: ItemType
    quantity: int
    unit_price: Decimal

    unit_cost: Decimal | None = None
    """What one of these had cost, as at the day it was sold.

    None means the item had never been bought, so nothing is known about
    what it cost — which is not the same as it having cost nothing. See
    `SaleItemModel.unit_cost`.
    """

    inventory_item_id: int | None = None
    sale_id: int | None = None

    previous_stock: int | None = None
    resulting_stock: int | None = None

    note: str | None = None
    id: int | None = None


    def __post_init__(self) -> None:

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_price < 0:
            raise ValueError("unit_price cannot be negative")
        if self.unit_cost is not None and self.unit_cost < 0:
            raise ValueError("unit_cost cannot be negative")

        # One id per item type, and the line has to carry the one its type
        # names — a special item module adds its own branch here alongside
        # its own column.
        if self.item_type is ItemType.INVENTORY_ITEM and self.inventory_item_id is None:
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM items")


    @property
    def total_amount(self) -> Decimal:
        return self.unit_price * Decimal(self.quantity)

    @property
    def cost_amount(self) -> Decimal | None:
        """What this line's stock cost, or None if that was never known."""
        if self.unit_cost is None:
            return None
        return self.unit_cost * Decimal(self.quantity)
