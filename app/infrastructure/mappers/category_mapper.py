from __future__ import annotations

from app.domain.entities.category import Category
from app.infrastructure.db.models.category_model import CategoryModel
from app.infrastructure.mappers.base import copy_shared_fields


class CategoryMapper:
    """Map between Category domain entities and ORM models."""

    @staticmethod
    def to_entity(model: CategoryModel) -> Category:
        entity = Category(
            name=model.name,
            description=model.description,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Category) -> CategoryModel:
        model = CategoryModel(
            name=entity.name,
            description=entity.description,
        )
        copy_shared_fields(entity, model)
        return model
