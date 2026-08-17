from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.domain.entities.base import AuditEntity


@dataclass(slots=True)
class InventoryMovement(AuditEntity):

    movement_type: MovementType
    item_type: ItemType
    quantity: int

    inventory_item_id: int | None = None

    source_document_type: str | None = None
    source_document_id: int | None = None

    unit_price: Decimal | None = None
    previous_stock: int | None = None
    resulting_stock: int | None = None

    reference_no: str | None = None
    note: str | None = None
    occurred_at: datetime | None = None
    reason: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        # See SaleItem: the movement carries the id its own item type names.
        if self.item_type is ItemType.INVENTORY_ITEM and self.inventory_item_id is None:
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM movements")

    @property
    def quantity_change(self) -> int:
        """How much this moved the count, with its sign.

        `quantity` is the size of the movement and is always positive; this
        is the movement. Read from the counts either side rather than from
        the type, because the type cannot answer it: a RETURN is stock
        coming back from a customer or going back to a supplier, and those
        move the count opposite ways.

        Falls back to the size when a movement was recorded without its
        before-and-after counts — older rows, and the only case where the
        sign genuinely is not known.
        """
        if self.previous_stock is None or self.resulting_stock is None:
            return self.quantity
        return self.resulting_stock - self.previous_stock
