from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.base import AuditEntity
from app.domain.quantities import to_quantity


@dataclass(slots=True, kw_only=True)
class SkuUnit(AuditEntity):
    """Another way to count one SKU: "a Box is 288 Pieces".

    Only the *alternates* are records. A SKU's base unit is the word on
    the SKU itself and is worth one of itself, so it needs no row and can
    never drift out of step with one. A document line naming no unit was
    entered in the base unit — which is why every line written before any
    of this existed is already correct.

    Deliberately not a unit system. There is no metre, no conversion
    between one SKU's Box and another's, and no graph to walk: a unit
    belongs to one SKU and converts to that SKU's base unit in one
    multiplication. A shop that buys in boxes and sells in pieces needs
    exactly that, and a measurement framework would be something else
    to maintain rather than something else it could do.
    """

    id: int | None = None
    sku_id: int
    name: str
    """What the shopkeeper calls it — "Box", "Packet", "Ream"."""

    factor: Decimal
    """How many base units one of these is. 1 Box = 288 Pieces is 288."""

    is_active: bool = True
    """Whether it may still be used on a new document.

    Retired rather than deleted: the documents that used it are still
    read back with it, and a unit that vanished would leave them naming
    nothing. See `set_sku_units`.
    """

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValueError("unit name cannot be empty")

        self.factor = to_quantity(self.factor)
        if self.factor <= 0:
            raise ValueError("a unit must be worth more than zero base units")

    def to_base(self, quantity: Decimal) -> Decimal:
        """`quantity` of these, counted in base units."""
        return to_quantity(to_quantity(quantity) * self.factor)
