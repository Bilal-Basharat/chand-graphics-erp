from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.base import TimestampEntity
from app.domain.enums.login_event_type import LoginEventType


@dataclass(slots=True)
class LoginAudit(TimestampEntity):
    id: int | None = None
    """Its own key, as every other entity carries. Without it a row that
    came out of the database could not be pointed at again — which the
    repository's own `get_by_id` and `delete` both need, and which is what
    dating a seeded history depends on."""

    user_id: int | None = None
    email: str = ""
    event_type: LoginEventType = LoginEventType.SIGN_IN_SUCCESS
    success: bool = True
    message: str | None = None
    app_version: str | None = None

    def __post_init__(self) -> None:
        self.email = self.email.strip().lower()
        if not self.email:
            raise ValueError("email cannot be empty")