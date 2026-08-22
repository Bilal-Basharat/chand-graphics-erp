from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.base import AuditEntity


@dataclass(slots=True, kw_only=True)
class Product(AuditEntity):
    """What the shop calls a thing it trades in — "A4 Ivory 250gsm".

    The business identity, above the stock identity. A product is what a
    customer asks for; the SKUs under it are the ones actually counted on
    a shelf, and most products have exactly one.

    Carries no stock, no unit and no price. Those belong to a SKU, and a
    product that held its own would be a second answer to the same
    question the moment it grew a second variant.
    """

    id: int | None = None
    name: str
    category_id: int
    """Which shelf it is listed on. Required: a product filed nowhere is
    a product that falls out of the catalogue, so there is a default
    category rather than an absent one."""

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValueError("name cannot be empty")
