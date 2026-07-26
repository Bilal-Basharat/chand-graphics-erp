from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.inventory_item import InventoryItem
from app.domain.repositories.base import Repository


class InventoryItemRepository(Repository[InventoryItem], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> InventoryItem | None:
        """Find an inventory item by name."""
        raise NotImplementedError

    @abstractmethod
    def list_low_stock(self, limit: int = 100) -> list[InventoryItem]:
        """Return items at or below minimum stock."""
        raise NotImplementedError