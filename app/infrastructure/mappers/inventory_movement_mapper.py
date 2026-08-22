from __future__ import annotations

from app.domain.entities.inventory_movement import InventoryMovement
from app.infrastructure.db.models.inventory_movement_model import InventoryMovementModel
from app.infrastructure.mappers.base import copy_shared_fields


class InventoryMovementMapper:
    """Map between InventoryMovement domain entities and ORM models."""

    @staticmethod
    def to_entity(model: InventoryMovementModel) -> InventoryMovement:
        entity = InventoryMovement(
            movement_type=model.movement_type,
            item_type=model.item_type,
            quantity=model.quantity,
            uom_id=model.uom_id,
            base_quantity=model.base_quantity,
            inventory_item_id=model.inventory_item_id,
            source_document_type=model.source_document_type,
            source_document_id=model.source_document_id,
            unit_price=model.unit_price,
            previous_stock=model.previous_stock,
            resulting_stock=model.resulting_stock,
            reference_no=model.reference_no,
            reason=model.reason,
            note=model.note,
            occurred_at=model.occurred_at,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: InventoryMovement) -> InventoryMovementModel:
        model = InventoryMovementModel(
            movement_type=entity.movement_type,
            item_type=entity.item_type,
            quantity=entity.quantity,
            uom_id=entity.uom_id,
            base_quantity=entity.base_quantity,
            inventory_item_id=entity.inventory_item_id,
            source_document_type=entity.source_document_type,
            source_document_id=entity.source_document_id,
            unit_price=entity.unit_price,
            previous_stock=entity.previous_stock,
            resulting_stock=entity.resulting_stock,
            reference_no=entity.reference_no,
            reason=entity.reason,
            note=entity.note,
            occurred_at=entity.occurred_at,
        )
        copy_shared_fields(entity, model)
        return model