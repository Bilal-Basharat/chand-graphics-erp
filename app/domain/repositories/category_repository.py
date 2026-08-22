from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

from app.domain.entities.category import Category
from app.domain.repositories.base import Repository


class CategoryRepository(Repository[Category], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> Category | None:
        """Find a category by name."""
        raise NotImplementedError

    @abstractmethod
    def page_categories(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Category]:
        """One page of categories, searched and ordered.

        Plain values rather than the application's page query: this is a
        domain port, and the layer that defines that query already depends
        on this one.
        """
        raise NotImplementedError

    @abstractmethod
    def count_categories(self, *, search: str = "") -> int:
        """How many categories that same search matches."""
        raise NotImplementedError

    @abstractmethod
    def names_by_id(self, category_ids: Collection[int]) -> dict[int, str]:
        """Category names for a set of ids, keyed by id.

        For naming the headings on one page of the catalogue without
        loading the categories to look them up in.
        """
        raise NotImplementedError
