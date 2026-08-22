from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.base import TimestampEntity
from app.domain.enums.item_type import ItemType
from app.domain.quantities import to_quantity


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

    quantity: Decimal
    """How many came back, in the unit the invoice line was sold in. It
    carries no unit of its own: a return is a reversal, and one measured
    differently from what it reverses could not be bounded by it."""

    base_quantity: Decimal | None = None
    """What came back, in base units, at the sale's own conversion.

    Taken from the line being reversed rather than from the SKU's units
    as they stand today, for the same reason its price is: reconfiguring
    a Box after the fact must not change how much stock a past return put
    back on the shelf.
    """

    unit_price: Decimal
    """Copied from the sale line rather than looked up.

    What the goods sold for is a fact about that invoice. Reading today's
    price would let a price change rewrite the value of a past return.
    """

    sale_return_id: int | None = None
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
        """What this line's goods were worth on the invoice."""
        return self.unit_price * self.quantity
