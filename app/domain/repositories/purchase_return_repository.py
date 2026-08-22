from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from app.domain.entities.purchase_return import PurchaseReturn
from app.domain.repositories.base import Repository


class PurchaseReturnRepository(Repository[PurchaseReturn], ABC):
    """Goods going back to suppliers — the mirror of `SaleReturnRepository`,
    and its own repository for the same reasons."""

    @abstractmethod
    def list_by_purchase_id(self, purchase_id: int) -> list[PurchaseReturn]:
        """Every return recorded against one purchase, oldest first."""
        raise NotImplementedError

    @abstractmethod
    def returned_quantity_for_line(self, purchase_item_id: int) -> Decimal:
        """How many of one purchase line have already gone back.

        The cap every new return is measured against: a line can send back
        what it bought and no more.
        """
        raise NotImplementedError

    @abstractmethod
    def returned_quantities_for_purchase(self, purchase_id: int) -> dict[int, Decimal]:
        """The same figure for every line of one purchase, in one query.

        What the return dialog needs to show "10 of 40 left" beside each
        line without asking per line.
        """
        raise NotImplementedError

    @abstractmethod
    def list_by_supplier(
        self,
        supplier_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[PurchaseReturn]:
        """Returns to one supplier in a date range, for their ledger.

        Dated by when the goods went back, not by when they were bought.
        """
        raise NotImplementedError

    @abstractmethod
    def credit_before(self, supplier_id: int, before: datetime) -> Decimal:
        """Value of everything sent back to one supplier before a moment."""
        raise NotImplementedError

    @abstractmethod
    def refund_before(self, supplier_id: int, before: datetime) -> Decimal:
        """Money they refunded against those returns."""
        raise NotImplementedError
