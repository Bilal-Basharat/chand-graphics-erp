from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SearchQuery:
    term: str
    limit: int = 50