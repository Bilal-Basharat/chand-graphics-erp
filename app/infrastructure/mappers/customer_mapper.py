from __future__ import annotations

from app.domain.entities.customer import Customer
from app.infrastructure.db.models.customer_model import CustomerModel
from app.infrastructure.mappers.base import copy_shared_fields


class CustomerMapper:
    """Map between Customer domain entities and ORM models."""

    @staticmethod
    def to_entity(model: CustomerModel) -> Customer:
        entity = Customer(
            name=model.name,
            phone=model.phone,
            address=model.address,
            notes=model.notes,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Customer) -> CustomerModel:
        model = CustomerModel(
            name=entity.name,
            phone=entity.phone,
            address=entity.address,
            notes=entity.notes,
        )
        copy_shared_fields(entity, model)
        return model