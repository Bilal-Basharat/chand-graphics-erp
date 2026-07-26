from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.expense_category import ExpenseCategory
from app.domain.repositories.base import Repository


class ExpenseCategoryRepository(Repository[ExpenseCategory], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> ExpenseCategory | None:
        """Find an expense category by name."""
        raise NotImplementedError