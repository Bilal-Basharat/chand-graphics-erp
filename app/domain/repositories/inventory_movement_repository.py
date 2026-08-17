from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.repositories.base import Repository


class InventoryMovementRepository(Repository[InventoryMovement], ABC):
    @abstractmethod
    def list_by_source_document(
        self,
        source_document_type: str,
        source_document_id: int,
        limit: int = 200,
    ) -> list[InventoryMovement]:
        """Return movements linked to a source document."""
        raise NotImplementedError

    @abstractmethod
    def page_movements(
        self,
        *,
        inventory_item_id: int,
        movement_type: str | None = None,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InventoryMovement]:
        """One page of one item's movement history."""
        raise NotImplementedError

    @abstractmethod
    def count_movements(
        self,
        *,
        inventory_item_id: int,
        movement_type: str | None = None,
        search: str = "",
    ) -> int:
        """How many movements those same conditions match."""
        raise NotImplementedError
