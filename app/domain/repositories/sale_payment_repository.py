from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from app.domain.entities.sale_payment import SalePayment
from app.domain.repositories.base import Repository


class SalePaymentRepository(Repository[SalePayment], ABC):
    @abstractmethod
    def list_by_sale_id(self, sale_id: int) -> list[SalePayment]:
        """Return all payments for one sale."""
        raise NotImplementedError

    @abstractmethod
    def sum_by_sale_id(self, sale_id: int) -> Decimal:
        """Return the total amount received so far against one sale."""
        raise NotImplementedError

    @abstractmethod
    def list_by_customer(
        self,
        customer_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[SalePayment]:
        """Everything received from one customer in a date range.

        Dated by when the money arrived, not by when the sale it settles
        was made — a payment belongs to the period it was received in.
        """
        raise NotImplementedError

    @abstractmethod
    def total_by_customer(self, customer_id: int, before: datetime) -> Decimal:
        """Total received from one customer before a moment in time."""
        raise NotImplementedError