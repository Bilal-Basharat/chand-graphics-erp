from __future__ import annotations

from app.domain.entities.card import Card
from app.infrastructure.db.models.card_model import CardModel
from app.infrastructure.mappers.base import copy_shared_fields


class CardMapper:
    """Map between Card domain entities and Card SQLAlchemy models."""

    @staticmethod
    def to_entity(model: CardModel) -> Card:
        entity = Card(
            card_number=model.card_number,
            name=model.name,
            purchase_price=model.purchase_price,
            selling_price=model.selling_price,
            current_stock=model.current_stock,
            minimum_stock=model.minimum_stock,
            cabinet_id=model.cabinet_id,
            description=model.description,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Card) -> CardModel:
        model = CardModel(
            card_number=entity.card_number,
            name=entity.name,
            purchase_price=entity.purchase_price,
            selling_price=entity.selling_price,
            current_stock=entity.current_stock,
            minimum_stock=entity.minimum_stock,
            cabinet_id=entity.cabinet_id,
            description=entity.description,
        )
        copy_shared_fields(entity, model)
        return model