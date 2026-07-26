from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.sale_payment import SalePayment
from app.domain.repositories.base import Repository


class SalePaymentRepository(Repository[SalePayment], ABC):
    @abstractmethod
    def list_by_sale_id(self, sale_id: int) -> list[SalePayment]:
        """Return all payments for one sale."""
        raise NotImplementedError