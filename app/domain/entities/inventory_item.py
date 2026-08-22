from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.base import AuditEntity
from app.domain.quantities import to_quantity

@dataclass(slots=True, kw_only=True)
class InventoryItem(AuditEntity):
    """
    A stocked catalogue record: paper, ink, packaging, anything counted.

    This is the SKU — the stock identity, the thing a count belongs to and
    the thing a document line names. The `Product` above it is the
    business identity, and most products have exactly one of these, which
    is why the catalogue screen shows the product and never says "SKU".

    Deliberately carries no price: purchase/selling price is only
    meaningful per transaction (PurchaseItem.unit_price /
    SaleItem.unit_price), since the same item is bought and sold at
    different prices over time. A single "current price" field here would
    silently overwrite that history every time a new price was recorded.
    """

    id: int | None = None
    name: str
    current_stock: Decimal = Decimal("0")
    minimum_stock: Decimal = Decimal("0")
    description: str | None = None

    product_id: int | None = None
    """Which product this is a variant of.

    Optional on the way in only: every SKU has one, and the use cases that
    make them say so. A database that predates products is brought up to
    date by `_add_catalogue_grouping`, which gives every item one.
    """

    cabinet_id: int | None = None
    """Where it is kept. Optional: an item nobody files still counts."""

    unit: str | None = None
    """What one of these is, in the shop's own words — "sheets", "ml",
    "bottles". This is the **base unit**: `current_stock` and
    `minimum_stock` are always a count of these, whatever unit a document
    was entered in. A SKU may be traded in others — see `SkuUnit` — and
    each of those says how many of these it is worth.

    Optional, because an item that is simply counted needs no word for it.
    """

    def __post_init__(self) -> None:

        if not self.name.strip():
            raise ValueError("name cannot be empty")
        if self.unit is not None:
            self.unit = " ".join(self.unit.split()) or None
        self.current_stock = to_quantity(self.current_stock)
        self.minimum_stock = to_quantity(self.minimum_stock)
        if self.current_stock < 0:
            raise ValueError("current_stock cannot be negative")
        if self.minimum_stock < 0:
            raise ValueError("minimum_stock cannot be negative")


    def receive_stock(self, quantity: Decimal) -> None:
        """Add `quantity` **base units** to the count."""

        quantity = to_quantity(quantity)
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        self.current_stock = to_quantity(self.current_stock + quantity)


    def issue_stock(self, quantity: Decimal) -> None:
        """Take `quantity` **base units** off the count."""

        quantity = to_quantity(quantity)
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if quantity > self.current_stock:
            raise ValueError("insufficient stock")
        self.current_stock = to_quantity(self.current_stock - quantity)


    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.minimum_stock
