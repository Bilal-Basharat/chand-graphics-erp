from __future__ import annotations

from abc import ABC, abstractmethod


class SessionStore(ABC):
    """
    Persistent session state for a desktop app.

    Stores only the signed-in user's identity reference.
    """

    @abstractmethod
    def save_user_id(self, user_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_user_id(self) -> int | None:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError