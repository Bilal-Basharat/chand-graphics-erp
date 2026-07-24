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

    card_id: int | None = None
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

    def __post_init__(self) -> None:

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        if self.item_type == ItemType.CARD:
            if self.card_id is None:
                raise ValueError("card_id is required for CARD movements")
            if self.inventory_item_id is not None:
                raise ValueError("inventory_item_id must be None for CARD movements")

        elif self.item_type == ItemType.INVENTORY_ITEM:
            if self.inventory_item_id is None:
                raise ValueError("inventory_item_id is required for INVENTORY_ITEM movements")
            if self.card_id is not None:
                raise ValueError("card_id must be None for INVENTORY_ITEM movements")