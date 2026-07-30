from __future__ import annotations

from app.domain.enums.login_event_type import LoginEventType
from dataclasses import dataclass


@dataclass(slots=True)
class SignInCommand:
    email: str
    password: str


@dataclass(slots=True)
class ChangePasswordCommand:
    current_password: str
    new_password: str


@dataclass(slots=True)
class EnsureInitialAdminUserCommand:
    email: str
    password: str
    full_name: str = "Administrator"
    role: str = "admin"

@dataclass(slots=True)
class RecordLoginAuditCommand:
    email: str
    event_type: LoginEventType
    user_id: int | None = None
    success: bool = True
    message: str | None = None
    app_version: str | None = None


@dataclass(slots=True)
class LoginHistoryQuery:
    user_id: int | None = None
    event_type: LoginEventType | None = None
    limit: int = 100
    offset: int = 0