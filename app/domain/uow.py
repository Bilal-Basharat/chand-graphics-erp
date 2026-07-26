# app/domain/uow.py
from __future__ import annotations

from abc import ABC, abstractmethod


class UnitOfWork(ABC):
    """
    Transaction boundary for application workflows.

    Use cases should depend on this abstraction, not on SQLAlchemy directly.
    """

    @abstractmethod
    def __enter__(self) -> UnitOfWork:
        raise NotImplementedError

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError