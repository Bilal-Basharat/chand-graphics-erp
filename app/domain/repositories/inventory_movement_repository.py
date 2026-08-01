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
    def list_by_card_id(self, card_id: int, limit: int = 200) -> list[InventoryMovement]:
        """Return the movement audit trail for a card."""
        raise NotImplementedError

    @abstractmethod
    def list_by_inventory_item_id(self, inventory_item_id: int, limit: int = 200) -> list[InventoryMovement]:
        """Return the movement audit trail for an inventory item."""
        raise NotImplementedError