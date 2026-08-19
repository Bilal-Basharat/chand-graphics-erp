from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.base import TimestampEntity
from app.domain.enums.item_type import ItemType


@dataclass(slots=True, kw_only=True)
class SaleReturnItem(TimestampEntity):
    """One line of goods coming back off an invoice.

    Anchored to `sale_item_id` rather than to an item: what may come back
    is bounded by what that invoice's line actually sold, and only the
    line can say so. Without it, stock that was never sold could be
    returned.
    """

    sale_item_id: int

    item_type: ItemType
    inventory_item_id: int | None = None

    quantity: int
    unit_price: Decimal
    """Copied from the sale line rather than looked up.

    What the goods sold for is a fact about that invoice. Reading today's
    price would let a price change rewrite the value of a past return.
    """

    sale_return_id: int | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.unit_price < 0:
            raise ValueError("unit_price cannot be negative")

        # See SaleItem: the line carries the id its own item type names.
        if self.item_type is ItemType.INVENTORY_ITEM and self.inventory_item_id is None:
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM returns")

    @property
    def total_amount(self) -> Decimal:
        """What this line's goods were worth on the invoice."""
        return self.unit_price * Decimal(self.quantity)
