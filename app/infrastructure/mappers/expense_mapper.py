from __future__ import annotations

from app.domain.entities.expense import Expense
from app.infrastructure.db.models.expense_model import ExpenseModel
from app.infrastructure.mappers.base import copy_shared_fields


class ExpenseMapper:
    """Map between Expense domain entities and ORM models."""

    @staticmethod
    def to_entity(model: ExpenseModel) -> Expense:
        entity = Expense(
            expense_name=model.expense_name,
            total_amount=model.total_amount,
            category_id=model.category_id,
            quantity=model.quantity,
            unit_price=model.unit_price,
            remarks=model.remarks,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Expense) -> ExpenseModel:
        total_amount = entity.total_amount
        if entity.quantity is not None and entity.unit_price is not None:
            total_amount = entity.unit_price * entity.quantity

        model = ExpenseModel(
            expense_name=entity.expense_name,
            category_id=entity.category_id,
            quantity=entity.quantity,
            unit_price=entity.unit_price,
            total_amount=total_amount,
            remarks=entity.remarks,
        )
        copy_shared_fields(entity, model)
        return model