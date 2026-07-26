from __future__ import annotations

from app.domain.entities.cabinet import Cabinet
from app.infrastructure.db.models.cabinet_model import CabinetModel
from app.infrastructure.mappers.base import copy_shared_fields


class CabinetMapper:
    """Map between Cabinet domain entities and ORM models."""

    @staticmethod
    def to_entity(model: CabinetModel) -> Cabinet:
        entity = Cabinet(
            code=model.code,
            description=model.description,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Cabinet) -> CabinetModel:
        model = CabinetModel(
            code=entity.code,
            description=entity.description,
        )
        copy_shared_fields(entity, model)
        return model