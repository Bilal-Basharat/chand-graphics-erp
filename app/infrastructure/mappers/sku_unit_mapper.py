from __future__ import annotations

from app.domain.entities.sku_unit import SkuUnit
from app.infrastructure.db.models.sku_unit_model import SkuUnitModel
from app.infrastructure.mappers.base import copy_shared_fields


class SkuUnitMapper:
    """Map between SkuUnit domain entities and ORM models."""

    @staticmethod
    def to_entity(model: SkuUnitModel) -> SkuUnit:
        entity = SkuUnit(
            sku_id=model.sku_id,
            name=model.name,
            factor=model.factor,
            is_active=model.is_active,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: SkuUnit) -> SkuUnitModel:
        model = SkuUnitModel(
            sku_id=entity.sku_id,
            name=entity.name,
            factor=entity.factor,
            is_active=entity.is_active,
        )
        copy_shared_fields(entity, model)
        return model
