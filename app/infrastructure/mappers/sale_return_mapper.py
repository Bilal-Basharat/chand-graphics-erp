from __future__ import annotations

from app.domain.entities.sale_return import SaleReturn
from app.infrastructure.db.models.sale_return_model import SaleReturnModel
from app.infrastructure.mappers.base import copy_shared_fields
from app.infrastructure.mappers.sale_return_item_mapper import SaleReturnItemMapper


class SaleReturnMapper:
    """Map between SaleReturn domain entities and ORM models."""

    @staticmethod
    def to_entity(model: SaleReturnModel) -> SaleReturn:
        entity = SaleReturn(
            return_no=model.return_no,
            sale_id=model.sale_id,
            refund_amount=model.refund_amount,
            refund_method_id=model.refund_method_id,
            reason=model.reason,
            note=model.note,
            returned_at=model.returned_at,
            items=[SaleReturnItemMapper.to_entity(item) for item in model.items],
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: SaleReturn) -> SaleReturnModel:
        model = SaleReturnModel(
            return_no=entity.return_no,
            sale_id=entity.sale_id,
            refund_amount=entity.refund_amount,
            refund_method_id=entity.refund_method_id,
            reason=entity.reason,
            note=entity.note,
            returned_at=entity.returned_at,
        )
        model.items = [SaleReturnItemMapper.to_model(item) for item in entity.items]

        copy_shared_fields(entity, model)
        return model
