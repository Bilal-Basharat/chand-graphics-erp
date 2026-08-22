from __future__ import annotations

from app.domain.entities.product import Product
from app.infrastructure.db.models.product_model import ProductModel
from app.infrastructure.mappers.base import copy_shared_fields


class ProductMapper:
    """Map between Product domain entities and ORM models."""

    @staticmethod
    def to_entity(model: ProductModel) -> Product:
        entity = Product(
            name=model.name,
            category_id=model.category_id,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Product) -> ProductModel:
        model = ProductModel(
            name=entity.name,
            category_id=entity.category_id,
        )
        copy_shared_fields(entity, model)
        return model
