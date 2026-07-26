from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.purchase import Purchase
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