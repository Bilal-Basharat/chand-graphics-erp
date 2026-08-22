"""
Finding the stocked record a document line moves, and moving it.

The one place that turns an `ItemType` into the catalogue behind it. A
special item module adds a branch to `load_stock_target` and nothing
else: sales, purchases and stock movements all reach their record through
here, so none of them has to know how many kinds there are.

It is also the one place a quantity is converted. Everything a shop
enters is in some unit — Boxes, Packets, Pieces — and everything a shelf
is counted in is the SKU's base unit. `to_base_quantity` is where the one
becomes the other, so a sale, a purchase, an adjustment and a return
cannot each round it their own way.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.entities.inventory_item import InventoryItem
from app.domain.enums.item_type import ItemType
from app.domain.quantities import to_quantity
from app.domain.uow import UnitOfWork
from app.application.exceptions import NotFoundError

ONE = Decimal("1")
"""What a base unit is worth in base units — and what a line that names no
unit was entered in."""


@dataclass(slots=True)
class ResolvedStockTarget:
    entity: InventoryItem
    repository: Any


def load_stock_target(
    uow: UnitOfWork,
    item_type: ItemType,
    inventory_item_id: int | None,
) -> ResolvedStockTarget:
    if item_type is ItemType.INVENTORY_ITEM:
        inventory_items = getattr(uow, "inventory_items", None)
        if inventory_items is None:
            raise RuntimeError("inventory_items repository is not initialized")
        if inventory_item_id is None:
            raise ValueError("inventory_item_id is required for INVENTORY_ITEM items")
        entity = inventory_items.get_by_id(inventory_item_id)
        if entity is None:
            raise NotFoundError(f"Inventory item id={inventory_item_id} not found")
        return ResolvedStockTarget(entity=entity, repository=inventory_items)

    raise ValueError(f"Unsupported item type: {item_type}")


def to_base_quantity(
    uow: UnitOfWork,
    item_type: ItemType,
    inventory_item_id: int | None,
    quantity: Decimal,
    uom_id: int | None,
) -> Decimal:
    """`quantity`, entered in unit `uom_id`, counted in base units.

    Validates as it converts, and refuses rather than guessing:

    * a unit that belongs to another SKU is the one way a quantity could
      be multiplied by a factor that has nothing to do with what is being
      traded, so the SKU is named in the lookup and never taken on trust;
    * a retired unit still explains the documents that used it, but
      nothing new may be entered in one.

    No unit named means the base unit, which is what every line written
    before units existed means, and what most lines will always mean.
    """
    quantity = to_quantity(quantity)
    if uom_id is None:
        return quantity

    if item_type is not ItemType.INVENTORY_ITEM:
        raise ValueError(f"{item_type} items are not traded in units")

    sku_units = getattr(uow, "sku_units", None)
    if sku_units is None:
        raise RuntimeError("sku_units repository is not initialized")

    unit = sku_units.get_for_sku(inventory_item_id, uom_id)
    if unit is None:
        raise NotFoundError(f"Unit id={uom_id} does not belong to this item")
    if not unit.is_active:
        raise ValueError(f"'{unit.name}' is no longer in use and cannot be entered.")

    return unit.to_base(quantity)


def returned_base_quantity(line: Any, quantity: Decimal) -> Decimal:
    """`quantity` off `line`, in base units, at that line's own conversion.

    Worked out from what the line stored rather than from the SKU's units
    as they stand now. A factor corrected this year must not change how
    much stock a return made last year put back on the shelf — and the
    line already holds both numbers the conversion needs.
    """
    quantity = to_quantity(quantity)
    return to_quantity(quantity * Decimal(line.base_quantity) / Decimal(line.quantity))


def increase_stock(entity: InventoryItem, quantity: Decimal) -> tuple[Decimal, Decimal]:
    """Put `quantity` **base units** on the shelf."""
    previous_stock = entity.current_stock
    entity.receive_stock(quantity)
    return previous_stock, entity.current_stock


def decrease_stock(entity: InventoryItem, quantity: Decimal) -> tuple[Decimal, Decimal]:
    """Take `quantity` **base units** off the shelf."""
    previous_stock = entity.current_stock
    entity.issue_stock(quantity)
    return previous_stock, entity.current_stock
