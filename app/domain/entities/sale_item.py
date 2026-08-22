from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.domain.entities.base import TimestampEntity
from app.domain.quantities import to_quantity


@dataclass(slots=True, kw_only=True)
class SaleItem(TimestampEntity):

    item_type: ItemType
    quantity: Decimal
    """How many were sold, in the unit the line was entered in."""

    unit_price: Decimal
    """What one of *those* sold for. A price is a price for the unit it
    was quoted in: 5,000 a Box is not 5,000 a Piece."""

    uom_id: int | None = None
    """Which of the SKU's units the line was entered in, or None for its
    base unit. Kept so the line reads back as it was written."""

    base_quantity: Decimal | None = None
    """The same quantity in the SKU's base unit — what stock and cost are
    actually counted in.

    Stored rather than worked out on demand, and this is the whole reason
    the column exists: re-deriving it would use today's conversion, so
    correcting a factor years later would silently restate every invoice
    that ever used it. Passed as None on the way in means "entered in the
    base unit"; it is never None afterwards.
    """

    unit_cost: Decimal | None = None
    """What one **base unit** of this had cost, as at the day it was sold.

    None means the item had never been bought, so nothing is known about
    what it cost — which is not the same as it having cost nothing. See
    `SaleItemModel.unit_cost`.
    """

    inventory_item_id: int | None = None
    sale_id: int | None = None

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
        if self.unit_cost is not None and self.unit_cost < 0:
            raise ValueError("unit_cost cannot be negative")

        # One id per item type, and the line has to carry the one its type
        # names — a special item module adds its own branch here alongside
        # its own column.
        if self.item_type is ItemType.INVENTORY_ITEM and self.inventory_item_id is None:
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM items")


    @property
    def total_amount(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def cost_amount(self) -> Decimal | None:
        """What this line's stock cost, or None if that was never known.

        Costed in base units on both sides: the average is per base unit,
        so the quantity multiplying it has to be as well, or a line sold
        by the Box would report a Box's worth of stock at a Piece's price.
        """
        if self.unit_cost is None:
            return None
        return self.unit_cost * self.base_quantity
