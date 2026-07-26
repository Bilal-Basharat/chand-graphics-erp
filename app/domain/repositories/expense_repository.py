from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.expense import Expense
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