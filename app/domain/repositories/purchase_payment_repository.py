from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from app.domain.entities.purchase_payment import PurchasePayment
from app.domain.repositories.base import Repository


class PurchasePaymentRepository(Repository[PurchasePayment], ABC):
    @abstractmethod
    def list_by_purchase_id(self, purchase_id: int) -> list[PurchasePayment]:
        """Return all payments for one purchase."""
        raise NotImplementedError

    @abstractmethod
    def sum_by_purchase_id(self, purchase_id: int) -> Decimal:
        """Return the total amount paid so far against one purchase."""
        raise NotImplementedError

    @abstractmethod
    def list_by_supplier(
        self,
        supplier_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[PurchasePayment]:
        """Everything paid to one supplier in a date range.

        Dated by when the money left, not by when the purchase it settles
        was made.
        """
        raise NotImplementedError

    @abstractmethod
    def total_by_supplier(self, supplier_id: int, before: datetime) -> Decimal:
        """Total paid to one supplier before a moment in time."""
        raise NotImplementedError