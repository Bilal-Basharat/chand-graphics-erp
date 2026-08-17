from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

from app.domain.entities.customer import Customer
from app.domain.repositories.base import Repository


class CustomerRepository(Repository[Customer], ABC):
    @abstractmethod
    def page_customers(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Customer]:
        """One page of customers, searched and ordered.

        Plain values rather than the application's page query: this is a
        domain port, and the layer that defines that query already depends
        on this one. A `sort_field` this repository does not offer falls
        back to its own order rather than refusing the page.
        """
        raise NotImplementedError

    @abstractmethod
    def count_customers(self, *, search: str = "") -> int:
        """How many customers that same search matches."""
        raise NotImplementedError

    @abstractmethod
    def names_by_id(self, customer_ids: Collection[int]) -> dict[int, str]:
        """Customer names for a set of ids, keyed by id.

        For naming the rows on one page of some other list without loading
        a table to look them up in — the same idea as
        `SaleRepository.numbers_by_id`.
        """
        raise NotImplementedError
