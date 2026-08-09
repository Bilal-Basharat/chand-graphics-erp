from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.domain.entities.base import AuditEntity

_USUALLY_INBOUND = frozenset({MovementType.RETURN, MovementType.ADJUSTMENT})
"""Which way a movement went, when the stock figures cannot say.

Only a fallback for rows recorded without them — see `quantity_change`,
which explains why the type alone is not an answer.
"""


@dataclass(slots=True)
class InventoryMovement(AuditEntity):

    movement_type: MovementType
    item_type: ItemType
    quantity: int
    """How many moved, always positive. Which way they went is
    `quantity_change`."""

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
    id: int | None = None

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

    @property
    def quantity_change(self) -> int:
        """Signed change to stock: positive put some in, negative took some out.

        Read from the two stock figures rather than guessed from the
        movement type, because the type does not know. An ADJUSTMENT goes
        either way — stock found or stock written off. So does a RETURN:
        a customer bringing goods back raises stock, the shop returning
        them to a supplier lowers it. A TRANSFER likewise. Only the before
        and after counts say which happened, and both are recorded.
        """
        if self.previous_stock is not None and self.resulting_stock is not None:
            return self.resulting_stock - self.previous_stock
        return (
            self.quantity
            if self.movement_type in _USUALLY_INBOUND
            else -self.quantity
        )