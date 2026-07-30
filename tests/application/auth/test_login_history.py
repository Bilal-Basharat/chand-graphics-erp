from __future__ import annotations

from app.application.auth.authorization import AuthorizationService
from app.application.auth.commands import LoginHistoryQuery, RecordLoginAuditCommand
from app.application.auth.login_audit_use_cases import ListLoginHistoryUseCase
from app.application.auth.session import CurrentUserSession
from app.domain.entities.user import User
from app.domain.enums.login_event_type import LoginEventType

from ._helpers import build_auth_bundle


def _make_admin_session() -> CurrentUserSession:
    session = CurrentUserSession()
    session.set_user(
        User(
            id=1,
            email="admin@example.com",
            password_hash="hashed",
            full_name="Admin User",
            role="admin",
            is_active=True,
        )
    )
    return session


def test_login_history_filters_by_user_id(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)

    bundle.audit_recorder.execute(
        RecordLoginAuditCommand(
            email="admin@example.com",
            user_id=1,
            event_type=LoginEventType.SIGN_IN_SUCCESS,
            success=True,
            message="Signed in",
        )
    )
    bundle.audit_recorder.execute(
        RecordLoginAuditCommand(
            email="admin@example.com",
            user_id=1,
            event_type=LoginEventType.SIGN_OUT,
            success=True,
            message="Signed out",
        )
    )
    bundle.audit_recorder.execute(
        RecordLoginAuditCommand(
            email="staff@example.com",
            user_id=2,
            event_type=LoginEventType.SIGN_IN_FAILURE,
            success=False,
            message="Wrong password",
        )
    )

    admin_session = _make_admin_session()
    authz = AuthorizationService(admin_session)
    use_case = ListLoginHistoryUseCase(uow, admin_session, authz)

    rows = use_case.execute(LoginHistoryQuery(user_id=1, limit=10))
    assert len(rows) == 2
    assert all(row.user_id == 1 for row in rows)


def test_login_history_filters_by_event_type(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)

    bundle.audit_recorder.execute(
        RecordLoginAuditCommand(
            email="admin@example.com",
            user_id=1,
            event_type=LoginEventType.SIGN_IN_SUCCESS,
            success=True,
            message="Signed in",
        )
    )
    bundle.audit_recorder.execute(
        RecordLoginAuditCommand(
            email="staff@example.com",
            user_id=2,
            event_type=LoginEventType.SIGN_IN_FAILURE,
            success=False,
            message="Wrong password",
        )
    )

    admin_session = _make_admin_session()
    authz = AuthorizationService(admin_session)
    use_case = ListLoginHistoryUseCase(uow, admin_session, authz)

    rows = use_case.execute(
        LoginHistoryQuery(event_type=LoginEventType.SIGN_IN_FAILURE, limit=10)
    )
    assert len(rows) == 1
    assert rows[0].event_type == LoginEventType.SIGN_IN_FAILURE
    assert rows[0].success is False