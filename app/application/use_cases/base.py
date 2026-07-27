from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")
T = TypeVar("T")


class UseCase(ABC, Generic[RequestT, ResponseT]):
    """
    Base class for application workflows.

    A use case coordinates repositories and the Unit of Work.
    It does not know about SQLAlchemy or the UI.
    """

    @abstractmethod
    def execute(self, request: RequestT) -> ResponseT:
        raise NotImplementedError

    @staticmethod
    def require(value: T | None, name: str) -> T:
        if value is None:
            raise RuntimeError(f"{name} repository is not initialized")
        return value