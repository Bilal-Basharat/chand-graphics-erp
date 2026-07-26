# app/infrastructure/repositories/base.py
from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

EntityT = TypeVar("EntityT")
ModelT = TypeVar("ModelT")


class EntityMapper(Protocol[EntityT, ModelT]):
    """
    Structural contract for mapping between domain entities and ORM models.

    A protocol does not need method implementations here.
    Any class with matching to_entity/to_model methods will satisfy it.
    """

    @staticmethod
    def to_entity(model: ModelT) -> EntityT:
        ...

    @staticmethod
    def to_model(entity: EntityT) -> ModelT:
        ...


class SQLAlchemyRepository(Generic[EntityT, ModelT]):
    """
    Generic repository implementation.

    Keeps SQLAlchemy isolated inside infrastructure and returns domain entities
    to the application layer.
    """

    def __init__(
        self,
        session: Session,
        model_class: type[ModelT],
        mapper: EntityMapper[EntityT, ModelT],
    ) -> None:
        self.session = session
        self.model_class = model_class
        self.mapper = mapper

    def add(self, entity: EntityT) -> EntityT:
        model = self.mapper.to_model(entity)
        self.session.add(model)
        self.session.flush()
        return self.mapper.to_entity(model)

    def update(self, entity: EntityT) -> EntityT:
        entity_id = getattr(entity, "id", None)
        if entity_id is None:
            raise ValueError("update() requires entity.id to be set")

        existing = self.session.get(self.model_class, entity_id)
        if existing is None:
            raise ValueError(f"{self.model_class.__name__} with id={entity_id} not found")

        updated_model = self.mapper.to_model(entity)
        setattr(updated_model, "id", entity_id)

        merged = self.session.merge(updated_model)
        self.session.flush()
        return self.mapper.to_entity(merged)

    def delete(self, entity_id: int) -> None:
        obj = self.session.get(self.model_class, entity_id)
        if obj is not None:
            self.session.delete(obj)
            self.session.flush()

    def get_by_id(self, entity_id: int) -> EntityT | None:
        model = self.session.get(self.model_class, entity_id)
        return None if model is None else self.mapper.to_entity(model)

    def list(self, limit: int = 100, offset: int = 0) -> list[EntityT]:
        stmt: Select[tuple[ModelT]] = select(self.model_class).offset(offset).limit(limit)
        models = self.session.execute(stmt).scalars().all()
        return [self.mapper.to_entity(model) for model in models]

    def find_one_by(self, column_name: str, value: object) -> EntityT | None:
        column = getattr(self.model_class, column_name)
        stmt = select(self.model_class).where(column == value)
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else self.mapper.to_entity(model)

    def find_all_by(self, column_name: str, value: object) -> list[EntityT]:
        column = getattr(self.model_class, column_name)
        stmt = select(self.model_class).where(column == value)
        models = self.session.execute(stmt).scalars().all()
        return [self.mapper.to_entity(model) for model in models]