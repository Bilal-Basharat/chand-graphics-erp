from __future__ import annotations

from app.domain.entities.supplier import Supplier
from app.infrastructure.db.models.supplier_model import SupplierModel
from app.infrastructure.mappers.base import copy_shared_fields


class SupplierMapper:
    """Map between Supplier domain entities and ORM models."""

    @staticmethod
    def to_entity(model: SupplierModel) -> Supplier:
        entity = Supplier(
            name=model.name,
            phone=model.phone,
            address=model.address,
            notes=model.notes,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Supplier) -> SupplierModel:
        model = SupplierModel(
            name=entity.name,
            phone=entity.phone,
            address=entity.address,
            notes=entity.notes,
        )
        copy_shared_fields(entity, model)
        return model