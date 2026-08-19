from __future__ import annotations

from app.domain.entities.purchase_return_item import PurchaseReturnItem
from app.infrastructure.db.models.purchase_return_item_model import PurchaseReturnItemModel
from app.infrastructure.mappers.base import copy_shared_fields


class PurchaseReturnItemMapper:
    """Map between PurchaseReturnItem domain entities and ORM models."""

    @staticmethod
    def to_entity(model: PurchaseReturnItemModel) -> PurchaseReturnItem:
        entity = PurchaseReturnItem(
            purchase_return_id=model.purchase_return_id,
            purchase_item_id=model.purchase_item_id,
            item_type=model.item_type,
            inventory_item_id=model.inventory_item_id,
            quantity=model.quantity,
            unit_price=model.unit_price,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: PurchaseReturnItem) -> PurchaseReturnItemModel:
        model = PurchaseReturnItemModel(
            purchase_item_id=entity.purchase_item_id,
            item_type=entity.item_type,
            inventory_item_id=entity.inventory_item_id,
            quantity=entity.quantity,
            unit_price=entity.unit_price,
        )
        copy_shared_fields(entity, model)
        return model
