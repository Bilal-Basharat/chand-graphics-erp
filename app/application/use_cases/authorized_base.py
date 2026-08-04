from __future__ import annotations

from abc import ABC
from typing import Generic, TypeVar

from app.application.auth.authorization import AuthorizationService
from app.application.auth.session import CurrentUserSession
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.domain.uow import UnitOfWork

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


class AuthorizedUnitOfWorkUseCase(
    AuthorizedUseCase[RequestT, ResponseT],
    ABC,
    Generic[RequestT, ResponseT],
):
    """
    An authorized use case whose work happens inside one unit of work.

    That is the shape of almost every write in this application, and the
    three-argument constructor that sets it up is the same every time. It
    is defined once here so a new use case is only its `execute`.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        session = current_user_session or CurrentUserSession()
        super().__init__(session, authorization_service or AuthorizationService(session))
        self.uow = uow