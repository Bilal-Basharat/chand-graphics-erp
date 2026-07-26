from __future__ import annotations

from app.domain.entities.user import User
from app.infrastructure.db.models.user_model import UserModel
from app.infrastructure.mappers.base import copy_shared_fields


class UserMapper:
    """Map between User domain entities and ORM models."""

    @staticmethod
    def to_entity(model: UserModel) -> User:
        entity = User(
            email=model.email,
            password_hash=model.password_hash,
            full_name=model.full_name,
            role=model.role,
            is_active=model.is_active,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: User) -> UserModel:
        model = UserModel(
            email=entity.email,
            password_hash=entity.password_hash,
            full_name=entity.full_name,
            role=entity.role,
            is_active=entity.is_active,
        )
        copy_shared_fields(entity, model)
        return model