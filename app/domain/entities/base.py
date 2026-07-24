from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, kw_only=True)

class TimestampEntity:
    created_at: datetime | None = None
    updated_at: datetime | None = None

class AuditEntity(TimestampEntity):
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None