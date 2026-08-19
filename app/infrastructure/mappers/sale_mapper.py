from __future__ import annotations

from app.domain.entities.sale import Sale
from app.infrastructure.db.models.sale_model import SaleModel
from app.infrastructure.mappers.base import copy_shared_fields
from app.infrastructure.mappers.sale_item_mapper import SaleItemMapper
from app.infrastructure.mappers.sale_payment_mapper import SalePaymentMapper


class SaleMapper:
    """Map between Sale domain entities and ORM models."""

    @staticmethod
    def to_entity(model: SaleModel) -> Sale:
        entity = Sale(
            invoice_no=model.invoice_no,
            customer_id=model.customer_id,
            note=model.note,
            discount_amount=model.discount_amount,
            returned_amount=model.returned_amount,
            refunded_amount=model.refunded_amount,
            items=[SaleItemMapper.to_entity(item) for item in getattr(model, "items", [])],
            payments=[SalePaymentMapper.to_entity(payment) for payment in getattr(model, "payments", [])],
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Sale) -> SaleModel:
        model = SaleModel(
            invoice_no=entity.invoice_no,
            customer_id=entity.customer_id,
            note=entity.note,
            discount_amount=entity.discount_amount,
            subtotal=entity.subtotal,
            grand_total=entity.grand_total,
            balance_amount=entity.balance_amount,
            # Every stored column is written on every save: this mapper
            # rebuilds the model from the entity, so a column left out
            # here is zeroed the next time a payment is recorded.
            returned_amount=entity.returned_amount,
            refunded_amount=entity.refunded_amount,
        )

        model.items = [SaleItemMapper.to_model(item) for item in entity.items]
        model.payments = [SalePaymentMapper.to_model(payment) for payment in entity.payments]

        copy_shared_fields(entity, model)
        return model