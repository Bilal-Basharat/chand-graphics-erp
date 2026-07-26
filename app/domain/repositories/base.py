from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

EntityT = TypeVar("EntityT")


class Repository(ABC, Generic[EntityT]):
    """
    Base contract for persistence operations.

    Implementations live in infrastructure.
    Domain and application layers depend only on this contract.
    """

    @abstractmethod
    def add(self, entity: EntityT) -> EntityT:
        """Persist a new entity and return it."""
        raise NotImplementedError

    @abstractmethod
    def update(self, entity: EntityT) -> EntityT:
        """Persist changes to an existing entity and return it."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, entity_id: int) -> None:
        """Delete an entity by its primary key."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, entity_id: int) -> EntityT | None:
        """Load a single entity by its primary key."""
        raise NotImplementedError

    @abstractmethod
    def list(self, limit: int = 100, offset: int = 0) -> list[EntityT]:
        """Return a paginated list of entities."""
        raise NotImplementedError