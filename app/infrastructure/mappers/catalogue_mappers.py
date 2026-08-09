"""Mappers for the two catalogues the job module introduces."""
from __future__ import annotations

from app.domain.entities.labour_charge_type import LabourChargeType
from app.domain.entities.product_type import ProductType
from app.infrastructure.db.models.labour_charge_type_model import LabourChargeTypeModel
from app.infrastructure.db.models.product_type_model import ProductTypeModel
from app.infrastructure.mappers.base import copy_shared_fields


class ProductTypeMapper:
    @staticmethod
    def to_entity(model: ProductTypeModel) -> ProductType:
        entity = ProductType(name=model.name, description=model.description)
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: ProductType) -> ProductTypeModel:
        model = ProductTypeModel(name=entity.name, description=entity.description)
        copy_shared_fields(entity, model)
        return model


class LabourChargeTypeMapper:
    @staticmethod
    def to_entity(model: LabourChargeTypeModel) -> LabourChargeType:
        entity = LabourChargeType(name=model.name, description=model.description)
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: LabourChargeType) -> LabourChargeTypeModel:
        model = LabourChargeTypeModel(name=entity.name, description=entity.description)
        copy_shared_fields(entity, model)
        return model
