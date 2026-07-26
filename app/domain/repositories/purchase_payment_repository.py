from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.purchase_payment import PurchasePayment
from app.domain.repositories.base import Repository


class PurchasePaymentRepository(Repository[PurchasePayment], ABC):
    @abstractmethod
    def list_by_purchase_id(self, purchase_id: int) -> list[PurchasePayment]:
        """Return all payments for one purchase."""
        raise NotImplementedError