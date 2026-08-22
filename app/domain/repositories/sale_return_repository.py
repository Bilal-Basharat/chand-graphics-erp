from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from app.domain.entities.sale_return import SaleReturn
from app.domain.repositories.base import Repository


class SaleReturnRepository(Repository[SaleReturn], ABC):
    """Goods coming back off sales.

    Deliberately its own repository rather than a collection on the sale.
    A return is validated against one line, listed against one document
    and totalled against one party, and none of those three want the whole
    invoice loaded to answer.
    """

    @abstractmethod
    def list_by_sale_id(self, sale_id: int) -> list[SaleReturn]:
        """Every return recorded against one sale, oldest first."""
        raise NotImplementedError

    @abstractmethod
    def returned_quantity_for_line(self, sale_item_id: int) -> Decimal:
        """How many of one sale line have already come back.

        The cap every new return is measured against: a line can give back
        what it sold and no more.
        """
        raise NotImplementedError

    @abstractmethod
    def returned_quantities_for_sale(self, sale_id: int) -> dict[int, Decimal]:
        """The same figure for every line of one sale, in one query.

        What the return dialog needs to show "10 of 40 left" beside each
        line without asking per line.
        """
        raise NotImplementedError

    @abstractmethod
    def list_by_customer(
        self,
        customer_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[SaleReturn]:
        """Returns from one customer in a date range, for their ledger.

        Dated by when the goods came back, not by when the sale was made.
        A walk-in sale carries no customer, so its returns never match here
        — which is exactly why no ledger shows them.
        """
        raise NotImplementedError

    @abstractmethod
    def credit_before(self, customer_id: int, before: datetime) -> Decimal:
        """Value of everything one customer returned before a moment."""
        raise NotImplementedError

    @abstractmethod
    def refund_before(self, customer_id: int, before: datetime) -> Decimal:
        """Money handed back to them against those returns."""
        raise NotImplementedError
