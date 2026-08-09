from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.base import AuditEntity


@dataclass(slots=True, kw_only=True)
class ProductType(AuditEntity):
    """What the shop can be asked to make: bill books, letterheads, cards.

    Carries no price — see Card for why. What a bill book sells for depends
    on its size, its paper and how many were ordered, so the price belongs
    to the job item that agreed it, not to the catalogue.
    """

    name: str
    description: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValueError("name cannot be empty")
