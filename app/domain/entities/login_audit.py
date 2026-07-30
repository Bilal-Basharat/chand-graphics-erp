from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.base import TimestampEntity
from app.domain.enums.login_event_type import LoginEventType


@dataclass(slots=True)
class LoginAudit(TimestampEntity):
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