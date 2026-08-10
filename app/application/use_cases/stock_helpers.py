"""
Finding the stocked record a document line moves, and moving it.

The one place that turns an `ItemType` into the catalogue behind it. A
special item module adds a branch to `load_stock_target` and nothing
else: sales, purchases and stock movements all reach their record through
here, so none of them has to know how many kinds there are.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.entities.inventory_item import InventoryItem
from app.domain.enums.item_type import ItemType
from app.domain.uow import UnitOfWork
from app.application.exceptions import NotFoundError


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


def increase_stock(entity: InventoryItem, quantity: int) -> tuple[int, int]:
    previous_stock = entity.current_stock
    entity.receive_stock(quantity)
    return previous_stock, entity.current_stock


def decrease_stock(entity: InventoryItem, quantity: int) -> tuple[int, int]:
    previous_stock = entity.current_stock
    entity.issue_stock(quantity)
    return previous_stock, entity.current_stock
