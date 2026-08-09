from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.job_order_entities import Job
from app.domain.enums.item_type import ItemType
from app.domain.repositories.base import Repository


class JobRepository(Repository[Job], ABC):
    @abstractmethod
    def get_by_job_no(self, job_no: str) -> Job | None:
        """Load a job by its number."""
        raise NotImplementedError

    @abstractmethod
    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ) -> list[Job]:
        """Return jobs in a date range."""
        raise NotImplementedError

    @abstractmethod
    def search_by_term(self, term: str, limit: int = 50) -> list[Job]:
        """Match on job number, customer name or note."""
        raise NotImplementedError

    @abstractmethod
    def count_by_material(self, item_type: ItemType, item_id: int) -> int:
        """How many jobs have consumed one card or inventory item."""
        raise NotImplementedError

    @abstractmethod
    def count_by_product_type(self, product_type_id: int) -> int:
        """How many jobs have been made against one product type."""
        raise NotImplementedError

    @abstractmethod
    def count_by_labour_charge_type(self, labour_charge_type_id: int) -> int:
        """How many jobs have been charged for one kind of work."""
        raise NotImplementedError

    @abstractmethod
    def count_by_customer(self, customer_id: int) -> int:
        """How many jobs are recorded against one customer."""
        raise NotImplementedError
