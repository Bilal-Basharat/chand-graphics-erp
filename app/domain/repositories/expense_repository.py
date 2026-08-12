from __future__ import annotations

from abc import ABC, abstractmethod
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