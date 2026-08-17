from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.domain.entities.login_audit import LoginAudit
from app.domain.enums.login_event_type import LoginEventType
from app.domain.repositories.login_audit_repository import LoginAuditRepository as LoginAuditRepositoryPort
from app.infrastructure.db.models.login_audit_model import LoginAuditModel
from app.infrastructure.mappers.login_audit_mapper import LoginAuditMapper
from app.infrastructure.repositories.base import SQLAlchemyRepository
from app.infrastructure.repositories.paging import contains, matching


class SqlAlchemyLoginAuditRepository(
    SQLAlchemyRepository[LoginAudit, LoginAuditModel],
    LoginAuditRepositoryPort,
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, LoginAuditModel, LoginAuditMapper)

    def list_recent(self, limit: int = 100, offset: int = 0) -> list[LoginAudit]:
        stmt = (
            select(LoginAuditModel)
            .order_by(LoginAuditModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [LoginAuditMapper.to_entity(model) for model in models]

    def list_by_user_id(self, user_id: int, limit: int = 100, offset: int = 0) -> list[LoginAudit]:
        stmt = (
            select(LoginAuditModel)
            .where(LoginAuditModel.user_id == user_id)
            .order_by(LoginAuditModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [LoginAuditMapper.to_entity(model) for model in models]

    def list_by_event_type(
        self,
        event_type: LoginEventType,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LoginAudit]:
        stmt = (
            select(LoginAuditModel)
            .where(LoginAuditModel.event_type == str(event_type))
            .order_by(LoginAuditModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [LoginAuditMapper.to_entity(model) for model in models]


    _SORTABLE = {
        "created": LoginAuditModel.created_at,
        "email": LoginAuditModel.email,
        "event": LoginAuditModel.event_type,
        "outcome": LoginAuditModel.success,
    }

    def _filtered_audits(self, user_id: int | None, event_type: str | None, search: str):
        stmt = select(LoginAuditModel)
        if user_id is not None:
            stmt = stmt.where(LoginAuditModel.user_id == user_id)
        if event_type:
            stmt = stmt.where(LoginAuditModel.event_type == str(event_type))
        if search:
            stmt = stmt.where(
                matching(contains(search), LoginAuditModel.email, LoginAuditModel.message)
            )
        return stmt

    def page_audits(
        self,
        *,
        user_id: int | None = None,
        event_type: str | None = None,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LoginAudit]:
        return self.page_of(
            self._filtered_audits(user_id, event_type, search),
            sortable=self._SORTABLE,
            default_sort="created",
            default_desc=True,
            sort_field=sort_field,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

    def count_audits(
        self,
        *,
        user_id: int | None = None,
        event_type: str | None = None,
        search: str = "",
    ) -> int:
        return self.count_of(self._filtered_audits(user_id, event_type, search))

    def count_recent_failed_sign_ins(self, email: str, since) -> int:
        stmt = (
            select(func.count())
            .select_from(LoginAuditModel)
            .where(LoginAuditModel.email == email.strip().lower())
            .where(LoginAuditModel.event_type == str(LoginEventType.SIGN_IN_FAILURE))
            .where(LoginAuditModel.success.is_(False))
            .where(LoginAuditModel.created_at >= since)
        )
        return int(self.session.execute(stmt).scalar_one())

    def count_recent_events(self, email: str, event_type: LoginEventType, since) -> int:
        stmt = (
            select(func.count())
            .select_from(LoginAuditModel)
            .where(LoginAuditModel.email == email.strip().lower())
            .where(LoginAuditModel.event_type == str(event_type))
            .where(LoginAuditModel.created_at >= since)
        )
        return int(self.session.execute(stmt).scalar_one())