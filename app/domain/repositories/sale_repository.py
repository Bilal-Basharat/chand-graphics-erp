from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from datetime import datetime
from decimal import Decimal

from app.domain.entities.sale import Sale
from app.domain.enums.item_type import ItemType
from app.domain.repositories.aggregates import (
    CostTotals,
    ItemMarginRow,
    OutstandingRow,
    RevenueTotals,
)
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
    def count_by_item(self, item_type: ItemType, item_id: int) -> int:
        """How many sales have sold one catalogue item."""
        raise NotImplementedError

    @abstractmethod
    def count_by_customer(self, customer_id: int) -> int:
        """How many sales are recorded against one customer."""
        raise NotImplementedError

    @abstractmethod
    def list_by_customer(
        self,
        customer_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[Sale]:
        """One customer's sales in a date range, oldest first.

        Oldest first because this feeds a statement, which is read from
        the top down.
        """
        raise NotImplementedError

    @abstractmethod
    def numbers_by_id(self, sale_ids: Collection[int]) -> dict[int, str]:
        """Invoice numbers for a set of sales, keyed by id.

        For listing payments without loading the sales they settle: a
        statement names the invoice each receipt was against, and nothing
        else about it.
        """
        raise NotImplementedError

    @abstractmethod
    def total_by_customer(self, customer_id: int, before: datetime) -> Decimal:
        """Total billed to one customer before a moment in time.

        The half of an opening balance that the sales themselves account
        for.
        """
        raise NotImplementedError

    ####################### reporting aggregates #######################
    # Unbounded on purpose. A report that answers about the first page of
    # a period is a report that is quietly wrong.

    @abstractmethod
    def revenue_between(self, start: datetime, end: datetime) -> RevenueTotals:
        """What was invoiced in a period, before and after discounts."""
        raise NotImplementedError

    @abstractmethod
    def cost_of_sales_between(self, start: datetime, end: datetime) -> CostTotals:
        """What the stock sold in a period had cost.

        Lines with no recorded cost are reported separately rather than
        counted as nothing, so a report can say what it does not know.
        """
        raise NotImplementedError

    @abstractmethod
    def margin_by_item_between(self, start: datetime, end: datetime) -> list[ItemMarginRow]:
        """Every item sold in a period, one row each."""
        raise NotImplementedError

    @abstractmethod
    def outstanding_before(self, as_at: datetime) -> list[OutstandingRow]:
        """Invoices with money still on them, oldest first."""
        raise NotImplementedError

    @abstractmethod
    def page_sales(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Sale]:
        """One page of a period's sales, searched, filtered and ordered.

        `payment` is a `PaymentFilter` value. Plain values rather than the
        application's page query: this is a domain port, and the layer
        that defines that query already depends on this one.
        """
        raise NotImplementedError

    @abstractmethod
    def count_sales(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
    ) -> int:
        """How many sales those same conditions match."""
        raise NotImplementedError

    @abstractmethod
    def sum_sales(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
    ) -> tuple[Decimal, Decimal]:
        """What they came to, and what is still owed on them.

        Over everything the conditions match, not over one page of it: a
        figure describing a period cannot be added up from a hundredth of
        it, and one that silently is would be wrong without ever failing.
        """
        raise NotImplementedError
