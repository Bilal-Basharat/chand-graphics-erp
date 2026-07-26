from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.cabinet import Cabinet
from app.domain.repositories.base import Repository


class CabinetRepository(Repository[Cabinet], ABC):
    @abstractmethod
    def get_by_code(self, code: str) -> Cabinet | None:
        """Find a cabinet by its code."""
        raise NotImplementedError