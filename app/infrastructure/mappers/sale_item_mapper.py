from __future__ import annotations

from app.domain.entities.sale_item import SaleItem
from app.infrastructure.db.models.sale_item_model import SaleItemModel
from app.infrastructure.mappers.base import copy_shared_fields


class SaleItemMapper:
    """Map between SaleItem domain entities and ORM models."""

    @staticmethod
    def to_entity(model: SaleItemModel) -> SaleItem:
        entity = SaleItem(
            item_type=model.item_type,
            quantity=model.quantity,
            uom_id=model.uom_id,
            base_quantity=model.base_quantity,
            unit_price=model.unit_price,
            unit_cost=model.unit_cost,
            sale_id=model.sale_id,
            inventory_item_id=model.inventory_item_id,
            previous_stock=model.previous_stock,
            resulting_stock=model.resulting_stock,
            note=model.note,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: SaleItem) -> SaleItemModel:
        model = SaleItemModel(
            sale_id=entity.sale_id,
            item_type=entity.item_type,
            inventory_item_id=entity.inventory_item_id,
            quantity=entity.quantity,
            uom_id=entity.uom_id,
            base_quantity=entity.base_quantity,
            unit_price=entity.unit_price,
            # Carried deliberately, not incidentally: `update()` rebuilds
            # this model from the entity and merges it by id, so a column
            # missing here is a column erased on the next payment.
            unit_cost=entity.unit_cost,
            line_total=entity.total_amount,
            previous_stock=entity.previous_stock,
            resulting_stock=entity.resulting_stock,
            note=entity.note,
        )
        copy_shared_fields(entity, model)
        return model