from __future__ import annotations

import logging

from app.application.auth.authorization import AuthorizationService
from app.application.auth.commands import (
    LoginHistoryPageQuery,
    LoginHistoryQuery,
    RecordLoginAuditCommand,
)
from app.application.auth.permissions import Permission
from app.application.auth.session import CurrentUserSession
from app.application.dto.queries import PageResult
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


class PageLoginHistoryUseCase(AuthorizedUseCase[LoginHistoryPageQuery, PageResult]):
    """One page of the sign-in history.

    Security-sensitive, like the listing below it, so it asks for the same
    permission. Paged because an installation a year old has thousands of
    these rows and the twenty-five that fitted on screen were never the
    interesting ones.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession,
        authorization_service: AuthorizationService,
    ) -> None:
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: LoginHistoryPageQuery) -> PageResult:
        self.require_permission(Permission.VIEW_REPORTS)

        with self.uow as uow:
            audits = self.require(uow.login_audits, "login_audits")
            conditions = {
                "user_id": request.user_id,
                "event_type": request.event_type,
                "search": request.search,
            }
            rows = audits.page_audits(
                **conditions,
                sort_field=request.sort_field,
                sort_desc=request.sort_desc,
                limit=request.page_size,
                offset=request.offset,
            )
            return PageResult(
                rows=rows,
                total=audits.count_audits(**conditions),
                page=request.page,
                page_size=request.page_size,
            )


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