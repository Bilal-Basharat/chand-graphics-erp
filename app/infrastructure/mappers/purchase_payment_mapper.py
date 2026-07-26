from __future__ import annotations

from app.domain.entities.purchase_payment import PurchasePayment
from app.infrastructure.db.models.purchase_payment_model import PurchasePaymentModel
from app.infrastructure.mappers.base import copy_shared_fields


class PurchasePaymentMapper:
    """Map between PurchasePayment domain entities and ORM models."""

    @staticmethod
    def to_entity(model: PurchasePaymentModel) -> PurchasePayment:
        entity = PurchasePayment(
            purchase_id=model.purchase_id,
            amount=model.amount,
            payment_method_id=model.payment_method_id,
            paid_by_user_id=model.paid_by_user_id,
            reference_no=model.reference_no,
            note=model.note,
            paid_at=model.paid_at,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: PurchasePayment) -> PurchasePaymentModel:
        model = PurchasePaymentModel(
            purchase_id=entity.purchase_id,
            amount=entity.amount,
            payment_method_id=entity.payment_method_id,
            paid_by_user_id=entity.paid_by_user_id,
            reference_no=entity.reference_no,
            note=entity.note,
            paid_at=entity.paid_at,
        )
        copy_shared_fields(entity, model)
        return model