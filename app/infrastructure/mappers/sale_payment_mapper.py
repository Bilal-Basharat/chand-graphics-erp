from __future__ import annotations

from app.domain.entities.sale_payment import SalePayment
from app.infrastructure.db.models.sale_payment_model import SalePaymentModel
from app.infrastructure.mappers.base import copy_shared_fields


class SalePaymentMapper:
    """Map between SalePayment domain entities and ORM models."""

    @staticmethod
    def to_entity(model: SalePaymentModel) -> SalePayment:
        entity = SalePayment(
            sale_id=model.sale_id,
            amount=model.amount,
            payment_method_id=model.payment_method_id,
            received_by_user_id=model.received_by_user_id,
            reference_no=model.reference_no,
            note=model.note,
            received_at=model.received_at,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: SalePayment) -> SalePaymentModel:
        model = SalePaymentModel(
            sale_id=entity.sale_id,
            amount=entity.amount,
            payment_method_id=entity.payment_method_id,
            received_by_user_id=entity.received_by_user_id,
            reference_no=entity.reference_no,
            note=entity.note,
            received_at=entity.received_at,
        )
        copy_shared_fields(entity, model)
        return model