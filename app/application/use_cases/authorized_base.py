from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar

from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class AuthorizedUseCase(
    AuthenticatedUseCase[RequestT, ResponseT],
    ABC,
    Generic[RequestT, ResponseT],
):
    """
    Base class for use cases that require a signed-in user and permissions.
    """

    def __init__(
        self,
        current_user_session,
        authorization_service: AuthorizationService,
    ) -> None:
        super().__init__(current_user_session)
        self.authorization_service = authorization_service

    def require_permission(self, permission: Permission) -> None:
        self.authorization_service.require(permission)