from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import datetime

from app.domain.entities.expense import Expense
from app.domain.repositories.aggregates import CategorySpendRow
from app.domain.repositories.base import Repository


class ExpenseRepository(Repository[Expense], ABC):
    @abstractmethod
    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[Expense]:
        """Return expenses within a date range."""
        raise NotImplementedError

    @abstractmethod
    def list_by_category(self, category_id: int, limit: int = 200) -> list[Expense]:
        """Return expenses for one category."""
        raise NotImplementedError

    @abstractmethod
    def count_by_category(self, category_id: int) -> int:
        """How many expenses are booked to one category."""
        raise NotImplementedError

    @abstractmethod
    def total_by_category_between(
        self, start: datetime, end: datetime
    ) -> list[CategorySpendRow]:
        """What was spent in a period, grouped by category.

        Unbounded: one row per category, however many expenses are behind
        them. A null category id is spending nobody filed.
        """
        raise NotImplementedError

    @abstractmethod
    def page_expenses(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        category_id: int | None = None,
        uncategorised: bool = False,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Expense]:
        """One page of a period's expenses.

        `uncategorised` is its own flag because a category id of None
        already means "every category" — an expense filed under nothing is
        a choice a screen offers, and the two cannot share one field.
        """
        raise NotImplementedError

    @abstractmethod
    def count_expenses(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        category_id: int | None = None,
        uncategorised: bool = False,
    ) -> int:
        """How many expenses those same conditions match."""
        raise NotImplementedError

    @abstractmethod
    def sum_expenses(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        category_id: int | None = None,
        uncategorised: bool = False,
    ) -> Decimal:
        """What the whole filtered period comes to, not one page of it."""
        raise NotImplementedError
