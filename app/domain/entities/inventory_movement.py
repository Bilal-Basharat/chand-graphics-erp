from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.domain.entities.base import AuditEntity
from app.domain.quantities import to_quantity


@dataclass(slots=True)
class InventoryMovement(AuditEntity):

    movement_type: MovementType
    item_type: ItemType
    quantity: Decimal

    inventory_item_id: int | None = None

    uom_id: int | None = None
    base_quantity: Decimal | None = None
    """See `SaleItem`: the unit this was recorded in, and what it came to
    in base units at the time. An adjustment counted in Boxes moves the
    shelf in Pieces, and the register has to show both."""

    source_document_type: str | None = None
    source_document_id: int | None = None

    unit_price: Decimal | None = None
    previous_stock: Decimal | None = None
    resulting_stock: Decimal | None = None

    reference_no: str | None = None
    note: str | None = None
    occurred_at: datetime | None = None
    reason: str | None = None
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

        # See SaleItem: the movement carries the id its own item type names.
        if self.item_type is ItemType.INVENTORY_ITEM and self.inventory_item_id is None:
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM movements")

    @property
    def quantity_change(self) -> Decimal:
        """How much this moved the count, with its sign, in base units.

        `quantity` is the size of the movement and is always positive; this
        is the movement. Read from the counts either side rather than from
        the type, because the type cannot answer it: a RETURN is stock
        coming back from a customer or going back to a supplier, and those
        move the count opposite ways.

        Falls back to `base_quantity` when a movement was recorded without
        its before-and-after counts — older rows, and the only case where
        the sign genuinely is not known. The base quantity rather than the
        entered one, because a count is what this is a change to.
        """
        if self.previous_stock is None or self.resulting_stock is None:
            return self.base_quantity
        return to_quantity(self.resulting_stock - self.previous_stock)
