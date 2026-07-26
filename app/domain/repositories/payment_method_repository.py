from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.payment_method import PaymentMethod
from app.domain.repositories.base import Repository


class PaymentMethodRepository(Repository[PaymentMethod], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> PaymentMethod | None:
        """Find a payment method by name."""
        raise NotImplementedError