from __future__ import annotations

from dataclasses import dataclass

from app.application.auth.exceptions import AuthenticationRequiredError
from app.domain.entities.user import User


@dataclass(slots=True, frozen=True)
class CurrentUser:
    user_id: int
    email: str
    full_name: str
    role: str


class CurrentUserSession:
    """
    In-process application session for the currently signed-in user.

    This is suitable for a desktop ERP where one process represents one user session.
    """

    def __init__(self) -> None:
        self._current_user: CurrentUser | None = None

    def set_user(self, user: User) -> None:
        if user.id is None:
            raise ValueError("User id must be set before storing session state")

        self._current_user = CurrentUser(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
        )

    def clear(self) -> None:
        self._current_user = None

    def is_authenticated(self) -> bool:
        return self._current_user is not None

    def get_user(self) -> CurrentUser | None:
        return self._current_user

    def require_user(self) -> CurrentUser:
        if self._current_user is None:
            raise AuthenticationRequiredError("User must sign in first")
        return self._current_user

    def require_user_id(self) -> int:
        return self.require_user().user_id