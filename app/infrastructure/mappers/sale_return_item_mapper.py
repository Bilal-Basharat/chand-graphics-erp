from __future__ import annotations

from app.domain.entities.sale_return_item import SaleReturnItem
from app.infrastructure.db.models.sale_return_item_model import SaleReturnItemModel
from app.infrastructure.mappers.base import copy_shared_fields


class SaleReturnItemMapper:
    """Map between SaleReturnItem domain entities and ORM models."""

    @staticmethod
    def to_entity(model: SaleReturnItemModel) -> SaleReturnItem:
        entity = SaleReturnItem(
            sale_return_id=model.sale_return_id,
            sale_item_id=model.sale_item_id,
            item_type=model.item_type,
            inventory_item_id=model.inventory_item_id,
            quantity=model.quantity,
            unit_price=model.unit_price,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: SaleReturnItem) -> SaleReturnItemModel:
        model = SaleReturnItemModel(
            sale_item_id=entity.sale_item_id,
            item_type=entity.item_type,
            inventory_item_id=entity.inventory_item_id,
            quantity=entity.quantity,
            unit_price=entity.unit_price,
        )
        copy_shared_fields(entity, model)
        return model
