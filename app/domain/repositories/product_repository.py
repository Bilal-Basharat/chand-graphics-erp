from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

from app.domain.entities.product import Product
from app.domain.repositories.base import Repository


class ProductRepository(Repository[Product], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> Product | None:
        """Find a product by name."""
        raise NotImplementedError

    @abstractmethod
    def page_catalogue(
        self,
        *,
        search: str = "",
        stock: str | None = None,
        category_id: int | None = None,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Product]:
        """One page of the catalogue, as the screen asks for it.

        Products, not SKUs — the catalogue is a list of things the shop
        trades in, and the variants under one of them are that row opened
        rather than more rows. Always ordered by category first, whatever
        else is asked for, so a page's categories are contiguous and each
        heading is written once.

        `search` matches the product's own name and the name and
        description of any of its SKUs; `stock` is a `StockFilter` and
        holds where any of its SKUs is at that level. Both reach through
        to the SKUs because that is where a shopkeeper's question actually
        lands: "what is low?" is never a question about a product.
        """
        raise NotImplementedError

    @abstractmethod
    def count_catalogue(
        self,
        *,
        search: str = "",
        stock: str | None = None,
        category_id: int | None = None,
    ) -> int:
        """How many products those same conditions match."""
        raise NotImplementedError

    @abstractmethod
    def count_in_category(self, category_id: int) -> int:
        """How many products are filed on that shelf."""
        raise NotImplementedError

    @abstractmethod
    def move_category(self, *, from_category_id: int, to_category_id: int) -> int:
        """Re-file every product on one shelf onto another, and return how
        many moved.

        Only the listing changes. Stock, units, prices and every document
        already written are untouched — a product is the same product
        wherever it is filed.
        """
        raise NotImplementedError

    @abstractmethod
    def names_by_id(self, product_ids: Collection[int]) -> dict[int, str]:
        """Product names for a set of ids, keyed by id."""
        raise NotImplementedError
