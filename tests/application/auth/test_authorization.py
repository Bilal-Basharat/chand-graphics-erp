from __future__ import annotations

import pytest

from app.application.auth.authorization import AuthorizationService
from app.application.auth.exceptions import PermissionDeniedError
from app.application.auth.permissions import Permission
from app.application.auth.session import CurrentUserSession
from app.domain.entities.user import User

from app.domain.enums.login_event_type import LoginEventType
from app.application.auth.commands import LoginHistoryQuery, RecordLoginAuditCommand
from app.application.auth.login_audit_use_cases import ListLoginHistoryUseCase
from app.application.auth.use_cases import SignInUseCase

from ._helpers import build_auth_bundle, seed_user

def _make_session(role: str) -> CurrentUserSession:
    session = CurrentUserSession()
    session.set_user(
        User(
            id=1,
            email=f"{role}@example.com",
            password_hash="hashed",
            full_name=f"{role.title()} User",
            role=role,
            is_active=True,
        )
    )
    return session


def test_admin_has_all_permissions():
    session = _make_session("admin")
    authz = AuthorizationService(session)

    assert authz.has(Permission.MANAGE_USERS) is True
    assert authz.has(Permission.MANAGE_SETTINGS) is True
    assert authz.has(Permission.MANAGE_PURCHASES) is True
    assert authz.has(Permission.MANAGE_SALES) is True
    assert authz.has(Permission.VIEW_REPORTS) is True


def test_staff_is_denied_users_permission():
    session = _make_session("staff")
    authz = AuthorizationService(session)

    assert authz.has(Permission.MANAGE_USERS) is False

    with pytest.raises(PermissionDeniedError):
        authz.require(Permission.MANAGE_USERS)


def test_manager_can_view_login_history(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)

    # Seed a few login audit rows.
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
            message="Invalid password",
        )
    )

    manager_session = _make_session("manager")
    authz = AuthorizationService(manager_session)

    use_case = ListLoginHistoryUseCase(uow, manager_session, authz)
    rows = use_case.execute(request=LoginHistoryQuery())

    assert len(rows) == 2


def test_staff_cannot_manage_users():
    session = _make_session("staff")
    authz = AuthorizationService(session)

    assert authz.has(Permission.MANAGE_USERS) is False

    with pytest.raises(PermissionDeniedError):
        authz.require(Permission.MANAGE_USERS)


def test_manager_can_manage_operations_but_not_users():
    session = _make_session("manager")
    authz = AuthorizationService(session)

    assert authz.has(Permission.MANAGE_PURCHASES) is True
    assert authz.has(Permission.MANAGE_SALES) is True
    assert authz.has(Permission.MANAGE_USERS) is False


def test_staff_cannot_view_login_history(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)

    staff_session = _make_session("staff")
    authz = AuthorizationService(staff_session)

    use_case = ListLoginHistoryUseCase(uow, staff_session, authz)

    with pytest.raises(PermissionDeniedError):
        use_case.execute(request=None)