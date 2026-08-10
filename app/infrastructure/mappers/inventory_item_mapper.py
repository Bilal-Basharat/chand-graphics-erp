from __future__ import annotations

from app.domain.entities.inventory_item import InventoryItem
from app.infrastructure.db.models.inventory_item_model import InventoryItemModel
from app.infrastructure.mappers.base import copy_shared_fields


class InventoryItemMapper:
    """Map between InventoryItem domain entities and ORM models."""

    @staticmethod
    def to_entity(model: InventoryItemModel) -> InventoryItem:
        entity = InventoryItem(
            name=model.name,
            current_stock=model.current_stock,
            minimum_stock=model.minimum_stock,
            description=model.description,
            cabinet_id=model.cabinet_id,
            unit=model.unit,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: InventoryItem) -> InventoryItemModel:
        model = InventoryItemModel(
            name=entity.name,
            current_stock=entity.current_stock,
            minimum_stock=entity.minimum_stock,
            description=entity.description,
            cabinet_id=entity.cabinet_id,
            unit=entity.unit,
        )
        copy_shared_fields(entity, model)
        return model