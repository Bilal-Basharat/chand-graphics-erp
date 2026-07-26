from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.user import User
from app.domain.repositories.base import Repository


class UserRepository(Repository[User], ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Find a user by email."""
        raise NotImplementedError