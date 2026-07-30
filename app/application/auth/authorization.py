from __future__ import annotations

from dataclasses import dataclass

from app.application.auth.exceptions import PermissionDeniedError
from app.application.auth.permissions import Permission, ROLE_PERMISSIONS
from app.application.auth.session import CurrentUserSession


@dataclass(slots=True)
class AuthorizationService:
    """
    Role-based authorization service.

    Uses the current signed-in user and checks whether the user's role
    allows a given permission.
    """

    current_user_session: CurrentUserSession

    def permissions_for_current_user(self) -> frozenset[Permission]:
        current_user = self.current_user_session.require_user()
        role = current_user.role.strip().lower()
        return ROLE_PERMISSIONS.get(role, frozenset())

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions_for_current_user()

    def require(self, permission: Permission) -> None:
        if not self.has(permission):
            current_user = self.current_user_session.require_user()
            raise PermissionDeniedError(
                f"User '{current_user.email}' does not have permission: {permission}"
            )