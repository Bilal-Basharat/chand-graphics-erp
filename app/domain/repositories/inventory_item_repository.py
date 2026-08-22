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
    def page_items(
        self,
        *,
        search: str = "",
        stock: str | None = None,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InventoryItem]:
        """One page of the catalogue, searched, filtered and ordered.

        Takes what it needs as plain values rather than the application's
        page query: a repository is a domain port, and the layer that
        defines that query already depends on this one.

        `stock` is a `StockFilter` value; `sort_field` is one of the names
        this repository offers, and anything else falls back to its own
        order rather than refusing the page.
        """
        raise NotImplementedError

    @abstractmethod
    def count_items(self, *, search: str = "", stock: str | None = None) -> int:
        """How many items those same conditions match."""
        raise NotImplementedError

    @abstractmethod
    def list_low_stock(self, limit: int = 100) -> list[InventoryItem]:
        """Return items at or below minimum stock."""
        raise NotImplementedError

    @abstractmethod
    def names_by_id(self, item_ids: Collection[int]) -> dict[int, str]:
        """Item names for a set of items, keyed by id.

        For naming what a report grouped by, without loading the items —
        the same idea as `SaleRepository.numbers_by_id`.
        """
        raise NotImplementedError

    @abstractmethod
    def list_by_product_ids(self, product_ids: Collection[int]) -> dict[int, list[InventoryItem]]:
        """The SKUs of several products at once, keyed by product id.

        One trip for a whole page of the catalogue. Fetched with the page
        rather than when a row is opened: a product's variants are few and
        already known by then, so a lazy fetch would buy nothing and add
        an asynchronous path through a table model.
        """
        raise NotImplementedError

    @abstractmethod
    def count_by_product(self, product_id: int) -> int:
        """How many SKUs a product has.

        What decides whether the catalogue shows a plain row or one that
        opens, and whether renaming the product renames its SKU too.
        """
        raise NotImplementedError

    @abstractmethod
    def clear_cabinet_id(self, cabinet_id: int) -> int:
        """Unfile every item in a cabinet, and return how many.

        A cabinet is where an item is kept, not what it is, so removing the
        cabinet leaves the items themselves untouched and merely unfiled.
        """
        raise NotImplementedError
