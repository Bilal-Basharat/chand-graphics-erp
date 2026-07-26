from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.supplier import Supplier
from app.domain.repositories.base import Repository


class SupplierRepository(Repository[Supplier], ABC):
    @abstractmethod
    def search_by_name(self, term: str, limit: int = 50) -> list[Supplier]:
        """Search suppliers by partial name match."""
        raise NotImplementedError