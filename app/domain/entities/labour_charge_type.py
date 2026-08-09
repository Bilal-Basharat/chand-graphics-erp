from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.base import AuditEntity


@dataclass(slots=True, kw_only=True)
class LabourChargeType(AuditEntity):
    """A kind of work the shop charges itself for: printing, binding,
    lamination, cutting.

    The catalogue only names the work. What it cost is decided per job item
    — binding ten bill books and binding five hundred wedding cards are the
    same kind of work at very different money — so the amount lives on
    `JobLabourCharge`, not here.
    """

    name: str
    description: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValueError("name cannot be empty")
