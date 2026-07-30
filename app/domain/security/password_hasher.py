from __future__ import annotations

from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    """
    Abstract password hashing contract.

    Infrastructure provides the concrete implementation.
    """

    @abstractmethod
    def hash(self, plain_text_password: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def verify(self, plain_text_password: str, hashed_password: str) -> bool:
        raise NotImplementedError