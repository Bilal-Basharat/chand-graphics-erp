from __future__ import annotations

from abc import ABC, abstractmethod
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
        """How many purchases have bought one card or inventory item."""
        raise NotImplementedError

    @abstractmethod
    def latest_unit_price(self, item_type: ItemType, item_id: int) -> Decimal | None:
        """What the shop last paid for one of these, or None if never bought.

        This is what a job material costs. The catalogue carries no price
        by design, so the most recent purchase is the only honest answer to
        "what is this worth" — and it is the answer a shopkeeper gives.
        """
        raise NotImplementedError

    @abstractmethod
    def count_by_supplier(self, supplier_id: int) -> int:
        """How many purchases are recorded against one supplier."""
        raise NotImplementedError
