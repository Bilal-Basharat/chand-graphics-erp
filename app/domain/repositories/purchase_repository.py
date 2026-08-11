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
    def search_by_term(self, term: str, limit: int = 50) -> list[Purchase]:
        """Match on purchase number, supplier name, reference or note."""
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
