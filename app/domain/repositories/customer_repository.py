from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.customer import Customer
from app.domain.repositories.base import Repository


class CustomerRepository(Repository[Customer], ABC):
    @abstractmethod
    def search_by_name(self, term: str, limit: int = 50) -> list[Customer]:
        """Search customers by partial name match."""
        raise NotImplementedError