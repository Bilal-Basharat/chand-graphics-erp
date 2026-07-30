from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.card import Card
from app.domain.repositories.base import Repository


class CardRepository(Repository[Card], ABC):
    @abstractmethod
    def get_by_card_number(self, card_number: str) -> Card | None:
        """Find a card by its business identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_low_stock(self, limit: int = 100) -> list[Card]:
        """Return cards at or below minimum stock."""
        raise NotImplementedError

    @abstractmethod
    def search_by_term(self, term: str, limit: int = 50) -> list[Card]:
        raise NotImplementedError