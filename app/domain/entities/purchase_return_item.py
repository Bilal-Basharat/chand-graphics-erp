from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.base import TimestampEntity
from app.domain.enums.item_type import ItemType
from app.domain.quantities import to_quantity


@dataclass(slots=True, kw_only=True)
class PurchaseReturnItem(TimestampEntity):
    """One line of goods going back off a purchase.

    The mirror of `SaleReturnItem`, anchored the same way: to the bill's
    line, so no more can go back than that bill actually bought.
    """

    purchase_item_id: int

    item_type: ItemType
    inventory_item_id: int | None = None

    quantity: Decimal
    base_quantity: Decimal | None = None
    """Both as on `SaleReturnItem`: counted in the unit the bill's line
    was bought in, and converted at that bill's own conversion."""

    unit_price: Decimal
    """Copied from the purchase line — see `SaleReturnItem.unit_price`."""

    purchase_return_id: int | None = None
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
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM returns")

    @property
    def total_amount(self) -> Decimal:
        """What this line's goods were worth on the bill."""
        return self.unit_price * self.quantity
