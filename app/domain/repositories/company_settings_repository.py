from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.company_settings import CompanySettings
from app.domain.repositories.base import Repository


class CompanySettingsRepository(Repository[CompanySettings], ABC):
    @abstractmethod
    def get_current(self) -> CompanySettings | None:
        """Return the active company settings row."""
        raise NotImplementedError