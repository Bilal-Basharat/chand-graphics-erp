"""Contracts for the two catalogues the job module introduces.

Same shape as each other — a named record looked up by name and searched
by term — so they are stated together rather than in two files that would
read identically.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.labour_charge_type import LabourChargeType
from app.domain.entities.product_type import ProductType
from app.domain.repositories.base import Repository


class ProductTypeRepository(Repository[ProductType], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> ProductType | None:
        raise NotImplementedError

    @abstractmethod
    def search_by_term(self, term: str, limit: int = 50) -> list[ProductType]:
        raise NotImplementedError


class LabourChargeTypeRepository(Repository[LabourChargeType], ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> LabourChargeType | None:
        raise NotImplementedError

    @abstractmethod
    def search_by_term(self, term: str, limit: int = 50) -> list[LabourChargeType]:
        raise NotImplementedError
