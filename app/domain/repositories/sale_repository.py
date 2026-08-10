from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.sale import Sale
from app.domain.enums.item_type import ItemType
from app.domain.repositories.base import Repository


class SaleRepository(Repository[Sale], ABC):
    @abstractmethod
    def get_by_invoice_no(self, invoice_no: str) -> Sale | None:
        """Load a sale by its invoice number."""
        raise NotImplementedError

    @abstractmethod
    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ) -> list[Sale]:
        """Return sales in a date range."""
        raise NotImplementedError

    @abstractmethod
    def search_by_term(self, term: str, limit: int = 50) -> list[Sale]:
        """Match on invoice number, customer name or note.

        The customer is included because people remember who they sold to
        far more readily than which invoice number it was.
        """
        raise NotImplementedError

    @abstractmethod
    def count_by_item(self, item_type: ItemType, item_id: int) -> int:
        """How many sales have sold one catalogue item."""
        raise NotImplementedError

    @abstractmethod
    def count_by_customer(self, customer_id: int) -> int:
        """How many sales are recorded against one customer."""
        raise NotImplementedError
