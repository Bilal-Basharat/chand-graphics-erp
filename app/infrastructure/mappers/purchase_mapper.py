from __future__ import annotations

from app.domain.entities.purchase import Purchase
from app.infrastructure.db.models.purchase_model import PurchaseModel
from app.infrastructure.mappers.base import copy_shared_fields
from app.infrastructure.mappers.purchase_item_mapper import PurchaseItemMapper
from app.infrastructure.mappers.purchase_payment_mapper import PurchasePaymentMapper


class PurchaseMapper:
    """Map between Purchase domain entities and ORM models."""

    @staticmethod
    def to_entity(model: PurchaseModel) -> Purchase:
        entity = Purchase(
            purchase_no=model.purchase_no,
            supplier_id=model.supplier_id,
            reference_no=model.reference_no,
            note=model.note,
            discount_amount=model.discount_amount,
            items=[PurchaseItemMapper.to_entity(item) for item in getattr(model, "items", [])],
            payments=[
                PurchasePaymentMapper.to_entity(payment)
                for payment in getattr(model, "payments", [])
            ],
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Purchase) -> PurchaseModel:
        model = PurchaseModel(
            purchase_no=entity.purchase_no,
            supplier_id=entity.supplier_id,
            reference_no=entity.reference_no,
            note=entity.note,
            discount_amount=entity.discount_amount,
            subtotal=entity.subtotal,
            grand_total=entity.grand_total,
            balance_amount=entity.balance_amount,
        )

        model.items = [PurchaseItemMapper.to_model(item) for item in entity.items]
        model.payments = [PurchasePaymentMapper.to_model(payment) for payment in entity.payments]

        copy_shared_fields(entity, model)
        return model