from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from datetime import datetime
from decimal import Decimal

from app.domain.entities.purchase import Purchase
from app.domain.enums.item_type import ItemType
from app.domain.repositories.base import Repository


class PurchaseRepository(Repository[Purchase], ABC):
    @abstractmethod
    def get_by_purchase_no(self, purchase_no: str) -> Purchase | None:
        """Load a purchase by its document number."""
        raise NotImplementedError

    @abstractmethod
    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ) -> list[Purchase]:
        """Return purchases in a date range."""
        raise NotImplementedError

    @abstractmethod
    def sum_by_supplier(self, supplier_id: int) -> Decimal:
        """Return total grand_total of all purchases from a supplier."""
        raise NotImplementedError

    @abstractmethod
    def count_by_item(self, item_type: ItemType, item_id: int) -> int:
        """How many purchases have bought one catalogue item."""
        raise NotImplementedError

    @abstractmethod
    def weighted_average_cost(self, item_type: ItemType, item_id: int) -> Decimal | None:
        """What one unit of an item has cost on average across every purchase.

        None when it has never been bought — which is not zero. It is what
        a sale line records as its cost, so that margin can be read later
        without the answer changing every time the item is bought again.
        """
        raise NotImplementedError

    @abstractmethod
    def count_by_supplier(self, supplier_id: int) -> int:
        """How many purchases are recorded against one supplier."""
        raise NotImplementedError

    @abstractmethod
    def list_by_supplier(
        self,
        supplier_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[Purchase]:
        """One supplier's purchases in a date range, oldest first.

        Oldest first because this feeds a statement, which is read from
        the top down.
        """
        raise NotImplementedError

    @abstractmethod
    def numbers_by_id(self, purchase_ids: Collection[int]) -> dict[int, str]:
        """Purchase numbers for a set of purchases, keyed by id.

        For listing payments without loading the purchases they settle.
        """
        raise NotImplementedError

    @abstractmethod
    def total_by_supplier(self, supplier_id: int, before: datetime) -> Decimal:
        """Total billed by one supplier before a moment in time.

        Unlike `sum_by_supplier`, which is every purchase ever, this is
        bounded — it is the half of an opening balance that the purchases
        themselves account for.
        """
        raise NotImplementedError

    @abstractmethod
    def page_purchases(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Purchase]:
        """One page of a period's purchases, searched, filtered and ordered.

        `payment` is a `PaymentFilter` value. Plain values rather than the
        application's page query: this is a domain port, and the layer
        that defines that query already depends on this one.
        """
        raise NotImplementedError

    @abstractmethod
    def count_purchases(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
    ) -> int:
        """How many purchases those same conditions match."""
        raise NotImplementedError

    @abstractmethod
    def sum_purchases(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
    ) -> tuple[Decimal, Decimal]:
        """What they came to, and what is still owed on them.

        Over everything the conditions match, not over one page of it: a
        figure describing a period cannot be added up from a hundredth of
        it, and one that silently is would be wrong without ever failing.
        """
        raise NotImplementedError
