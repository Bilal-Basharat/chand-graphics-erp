from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

from app.domain.entities.payment_method import PaymentMethod
from app.domain.repositories.base import Repository


class PaymentMethodRepository(Repository[PaymentMethod], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> PaymentMethod | None:
        """Find a payment method by name."""
        raise NotImplementedError

    @abstractmethod
    def page_payment_methods(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentMethod]:
        """One page of payment methods, searched and ordered.

        Plain values rather than the application's page query: this is a
        domain port, and the layer that defines that query already depends
        on this one. A `sort_field` this repository does not offer falls
        back to its own order rather than refusing the page.
        """
        raise NotImplementedError

    @abstractmethod
    def count_payment_methods(self, *, search: str = "") -> int:
        """How many payment methods that same search matches."""
        raise NotImplementedError

    @abstractmethod
    def names_by_id(self, method_ids: Collection[int]) -> dict[int, str]:
        """Method names for a set of ids, keyed by id.

        For naming the rows on one page of some other list without loading
        a table to look them up in — the same idea as
        `SaleRepository.numbers_by_id`.
        """
        raise NotImplementedError
