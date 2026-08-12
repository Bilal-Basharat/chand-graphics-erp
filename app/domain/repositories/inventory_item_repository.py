from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

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

    @abstractmethod
    def search_by_term(self, term: str, limit: int = 50) -> list[InventoryItem]:
        raise NotImplementedError

    @abstractmethod
    def names_by_id(self, item_ids: Collection[int]) -> dict[int, str]:
        """Item names for a set of items, keyed by id.

        For naming what a report grouped by, without loading the items —
        the same idea as `SaleRepository.numbers_by_id`.
        """
        raise NotImplementedError

    @abstractmethod
    def clear_cabinet_id(self, cabinet_id: int) -> int:
        """Unfile every item in a cabinet, and return how many.

        A cabinet is where an item is kept, not what it is, so removing the
        cabinet leaves the items themselves untouched and merely unfiled.
        """
        raise NotImplementedError
