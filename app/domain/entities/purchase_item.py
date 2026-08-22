from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.domain.entities.base import TimestampEntity
from app.domain.quantities import to_quantity


@dataclass(slots=True, kw_only=True)
class PurchaseItem(TimestampEntity):

    item_type: ItemType
    quantity: Decimal
    unit_price: Decimal

    uom_id: int | None = None
    base_quantity: Decimal | None = None
    """See `SaleItem` for both: the unit the line was bought in, and what
    that came to in base units at the time."""

    inventory_item_id: int | None = None
    purchase_id: int | None = None

    previous_stock: Decimal | None = None
    resulting_stock: Decimal | None = None

    note: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:

        self.quantity = to_quantity(self.quantity)
        self.base_quantity = to_quantity(
            self.quantity if self.base_quantity is None else self.base_quantity
        )
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.base_quantity <= 0:
            raise ValueError("base_quantity must be greater than zero")
        if self.unit_price < 0:
            raise ValueError("unit_price cannot be negative")

        # See SaleItem: the line carries the id its own item type names.
        if self.item_type is ItemType.INVENTORY_ITEM and self.inventory_item_id is None:
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM items")

    @property
    def total_amount(self) -> Decimal:
        return self.unit_price * self.quantity
