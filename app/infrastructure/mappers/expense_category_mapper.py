from __future__ import annotations

from app.domain.entities.expense_category import ExpenseCategory
from app.infrastructure.db.models.expense_category_model import ExpenseCategoryModel
from app.infrastructure.mappers.base import copy_shared_fields


class ExpenseCategoryMapper:
    """Map between ExpenseCategory domain entities and ORM models."""

    @staticmethod
    def to_entity(model: ExpenseCategoryModel) -> ExpenseCategory:
        entity = ExpenseCategory(
            name=model.name,
            description=model.description,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: ExpenseCategory) -> ExpenseCategoryModel:
        model = ExpenseCategoryModel(
            name=entity.name,
            description=entity.description,
        )
        copy_shared_fields(entity, model)
        return model