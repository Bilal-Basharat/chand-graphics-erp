from __future__ import annotations

import pytest

from app.application.auth.commands import SignInCommand
from app.application.auth.exceptions import InactiveAccountError, InvalidCredentialsError
from app.application.auth.login_audit_use_cases import RecordLoginAuditUseCase
from app.application.auth.session import CurrentUserSession
from app.application.auth.use_cases import SignInUseCase, SignOutUseCase
from app.domain.enums.login_event_type import LoginEventType

from ._helpers import build_auth_bundle, seed_user


def test_sign_in_success_sets_session_and_writes_audit(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)
    seed_user(uow, bundle.hasher)

    use_case = SignInUseCase(
        uow,
        bundle.hasher,
        bundle.current_user_session,
        bundle.session_store,
        bundle.audit_recorder,
    )

    result = use_case.execute(
        SignInCommand(email="admin@example.com", password="secret123")
    )

    assert result.email == "admin@example.com"
    assert result.role == "admin"
    assert bundle.current_user_session.is_authenticated() is True
    assert bundle.session_store.load_user_id() == result.user_id

    with uow as tx:
        audits = tx.login_audits
        assert audits is not None

        rows = audits.list_recent(limit=10)
        assert len(rows) == 1
        assert rows[0].event_type == LoginEventType.SIGN_IN_SUCCESS
        assert rows[0].success is True
        assert rows[0].email == "admin@example.com"


def test_sign_in_wrong_password_records_failure_audit(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)
    seed_user(uow, bundle.hasher)

    use_case = SignInUseCase(
        uow,
        bundle.hasher,
        bundle.current_user_session,
        bundle.session_store,
        bundle.audit_recorder,
    )

    with pytest.raises(InvalidCredentialsError):
        use_case.execute(
            SignInCommand(email="admin@example.com", password="wrong-password")
        )

    assert bundle.current_user_session.is_authenticated() is False
    assert bundle.session_store.load_user_id() is None

    with uow as tx:
        audits = tx.login_audits
        assert audits is not None

        rows = audits.list_recent(limit=10)
        assert len(rows) == 1
        assert rows[0].event_type == LoginEventType.SIGN_IN_FAILURE
        assert rows[0].success is False
        assert rows[0].email == "admin@example.com"


def test_sign_in_inactive_user_records_failure_audit(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)
    seed_user(uow, bundle.hasher, is_active=False)

    use_case = SignInUseCase(
        uow,
        bundle.hasher,
        bundle.current_user_session,
        bundle.session_store,
        bundle.audit_recorder,
    )

    with pytest.raises(InactiveAccountError):
        use_case.execute(
            SignInCommand(email="admin@example.com", password="secret123")
        )

    assert bundle.current_user_session.is_authenticated() is False
    assert bundle.session_store.load_user_id() is None

    with uow as tx:
        audits = tx.login_audits
        assert audits is not None

        rows = audits.list_recent(limit=10)
        assert len(rows) == 1
        assert rows[0].event_type == LoginEventType.SIGN_IN_FAILURE
        assert rows[0].success is False


def test_sign_out_clears_session_and_records_audit(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)
    seed_user(uow, bundle.hasher)

    sign_in = SignInUseCase(
        uow,
        bundle.hasher,
        bundle.current_user_session,
        bundle.session_store,
        bundle.audit_recorder,
    )
    sign_in.execute(SignInCommand(email="admin@example.com", password="secret123"))

    sign_out = SignOutUseCase(
        bundle.current_user_session,
        bundle.session_store,
        bundle.audit_recorder,
    )
    sign_out.execute()

    assert bundle.current_user_session.is_authenticated() is False
    assert bundle.session_store.load_user_id() is None

    with uow as tx:
        audits = tx.login_audits
        assert audits is not None

        rows = audits.list_recent(limit=10)
        assert len(rows) == 2
        assert rows[0].event_type == LoginEventType.SIGN_OUT
        assert rows[0].success is True