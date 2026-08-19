from __future__ import annotations

from app.domain.entities.purchase_return import PurchaseReturn
from app.infrastructure.db.models.purchase_return_model import PurchaseReturnModel
from app.infrastructure.mappers.base import copy_shared_fields
from app.infrastructure.mappers.purchase_return_item_mapper import PurchaseReturnItemMapper


class PurchaseReturnMapper:
    """Map between PurchaseReturn domain entities and ORM models."""

    @staticmethod
    def to_entity(model: PurchaseReturnModel) -> PurchaseReturn:
        entity = PurchaseReturn(
            return_no=model.return_no,
            purchase_id=model.purchase_id,
            refund_amount=model.refund_amount,
            refund_method_id=model.refund_method_id,
            reason=model.reason,
            note=model.note,
            returned_at=model.returned_at,
            items=[PurchaseReturnItemMapper.to_entity(item) for item in model.items],
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: PurchaseReturn) -> PurchaseReturnModel:
        model = PurchaseReturnModel(
            return_no=entity.return_no,
            purchase_id=entity.purchase_id,
            refund_amount=entity.refund_amount,
            refund_method_id=entity.refund_method_id,
            reason=entity.reason,
            note=entity.note,
            returned_at=entity.returned_at,
        )
        model.items = [PurchaseReturnItemMapper.to_model(item) for item in entity.items]

        copy_shared_fields(entity, model)
        return model
