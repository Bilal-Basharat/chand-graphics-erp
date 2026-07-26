from __future__ import annotations

from app.domain.entities.purchase_item import PurchaseItem
from app.infrastructure.db.models.purchase_item_model import PurchaseItemModel
from app.infrastructure.mappers.base import copy_shared_fields


class PurchaseItemMapper:
    """Map between PurchaseItem domain entities and ORM models."""

    @staticmethod
    def to_entity(model: PurchaseItemModel) -> PurchaseItem:
        entity = PurchaseItem(
            item_type=model.item_type,
            quantity=model.quantity,
            unit_price=model.unit_price,
            purchase_id=model.purchase_id,
            card_id=model.card_id,
            inventory_item_id=model.inventory_item_id,
            previous_stock=model.previous_stock,
            resulting_stock=model.resulting_stock,
            note=model.note,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: PurchaseItem) -> PurchaseItemModel:
        model = PurchaseItemModel(
            purchase_id=entity.purchase_id,
            item_type=entity.item_type,
            card_id=entity.card_id,
            inventory_item_id=entity.inventory_item_id,
            quantity=entity.quantity,
            unit_price=entity.unit_price,
            total_amount=entity.total_amount,
            previous_stock=entity.previous_stock,
            resulting_stock=entity.resulting_stock,
            note=entity.note,
        )
        copy_shared_fields(entity, model)
        return model