from __future__ import annotations

import logging

from app.application.auth.authorization import AuthorizationService
from app.application.auth.commands import LoginHistoryQuery, RecordLoginAuditCommand
from app.application.auth.permissions import Permission
from app.application.auth.session import CurrentUserSession
from app.application.use_cases.authorized_base import AuthorizedUseCase
from app.application.use_cases.base import UseCase
from app.domain.entities.login_audit import LoginAudit
from app.domain.uow import UnitOfWork

logger = logging.getLogger(__name__)


class RecordLoginAuditUseCase(UseCase[RecordLoginAuditCommand, LoginAudit]):
    """
    Writes a login audit record using its own unit of work.
    This keeps audit writes independent from sign-in/sign-out success or failure.
    """

    def __init__(self, uow: UnitOfWork, app_version: str) -> None:
        self.uow = uow
        self.app_version = app_version

    def execute(self, request: RecordLoginAuditCommand) -> LoginAudit:
        with self.uow as uow:
            audits = self.require(uow.login_audits, "login_audits")

            audit = LoginAudit(
                user_id=request.user_id,
                email=request.email,
                event_type=request.event_type,
                success=request.success,
                message=request.message,
                app_version=request.app_version or self.app_version,
            )
            return audits.add(audit)


class ListLoginHistoryUseCase(AuthorizedUseCase[LoginHistoryQuery, list[LoginAudit]]):
    """
    Security-sensitive history query. Requires report permission.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession,
        authorization_service: AuthorizationService,
    ) -> None:
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: LoginHistoryQuery) -> list[LoginAudit]:
        self.require_permission(Permission.VIEW_REPORTS)

        with self.uow as uow:
            audits = self.require(uow.login_audits, "login_audits")

            if request.user_id is not None:
                return audits.list_by_user_id(request.user_id, request.limit, request.offset)

            if request.event_type is not None:
                return audits.list_by_event_type(request.event_type, request.limit, request.offset)

            return audits.list_recent(request.limit, request.offset)