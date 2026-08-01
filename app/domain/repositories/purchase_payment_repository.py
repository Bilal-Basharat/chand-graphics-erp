from __future__ import annotations

from abc import ABC, abstractmethod
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