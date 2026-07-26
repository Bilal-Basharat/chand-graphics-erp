from __future__ import annotations

from app.domain.entities.payment_method import PaymentMethod
from app.infrastructure.db.models.payment_method_model import PaymentMethodModel
from app.infrastructure.mappers.base import copy_shared_fields


class PaymentMethodMapper:
    """Map between PaymentMethod domain entities and ORM models."""

    @staticmethod
    def to_entity(model: PaymentMethodModel) -> PaymentMethod:
        entity = PaymentMethod(name=model.name)
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: PaymentMethod) -> PaymentMethodModel:
        model = PaymentMethodModel(name=entity.name)
        copy_shared_fields(entity, model)
        return model