from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

from app.domain.entities.expense_category import ExpenseCategory
from app.domain.repositories.base import Repository


class ExpenseCategoryRepository(Repository[ExpenseCategory], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> ExpenseCategory | None:
        """Find an expense category by name."""
        raise NotImplementedError

    @abstractmethod
    def page_expense_categories(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExpenseCategory]:
        """One page of expense categories, searched and ordered.

        Plain values rather than the application's page query: this is a
        domain port, and the layer that defines that query already depends
        on this one. A `sort_field` this repository does not offer falls
        back to its own order rather than refusing the page.
        """
        raise NotImplementedError

    @abstractmethod
    def count_expense_categories(self, *, search: str = "") -> int:
        """How many expense categories that same search matches."""
        raise NotImplementedError

    @abstractmethod
    def names_by_id(self, category_ids: Collection[int]) -> dict[int, str]:
        """Category names for a set of ids, keyed by id.

        For naming the rows on one page of some other list without loading
        a table to look them up in — the same idea as
        `SaleRepository.numbers_by_id`.
        """
        raise NotImplementedError
