from __future__ import annotations

from app.application.auth.commands import SignInCommand
from app.application.auth.login_audit_use_cases import RecordLoginAuditUseCase
from app.application.auth.use_cases import RestoreSessionUseCase, SignInUseCase
from app.application.auth.session import CurrentUserSession
from app.domain.entities.user import User
from app.infrastructure.auth.file_session_store import FileSessionStore
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from app.domain.enums.login_event_type import LoginEventType
from ._helpers import build_auth_bundle, seed_user

def test_restore_session_loads_user_and_records_audit(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)
    user = seed_user(uow, bundle.hasher)

    bundle.session_store.save_user_id(user.id)  # type: ignore[arg-type]

    restored_session = CurrentUserSession()
    restore = RestoreSessionUseCase(
        uow,
        restored_session,
        bundle.session_store,
        bundle.audit_recorder,
    )

    restored = restore.execute()

    assert restored is not None
    assert restored.email == "admin@example.com"
    assert restored_session.is_authenticated() is True
    assert bundle.session_store.load_user_id() == user.id

    with uow as tx:
        audits = tx.login_audits
        assert audits is not None

        rows = audits.list_recent(limit=10)
        assert len(rows) == 1
        assert rows[0].event_type == LoginEventType.SESSION_RESTORED
        assert rows[0].success is True

def test_sign_in_saves_session_and_restore_loads_it(uow, tmp_path):
    hasher = BcryptPasswordHasher()
    session_store = FileSessionStore(tmp_path / "session.json")
    current_user_session = CurrentUserSession()

    with uow as tx:
        users = tx.users
        assert users is not None

        users.add(
            User(
                email="admin@example.com",
                password_hash=hasher.hash("secret123"),
                full_name="Admin User",
                role="admin",
                is_active=True,
            )
        )

    sign_in = SignInUseCase(
        uow,
        hasher,
        current_user_session,
        session_store,
        RecordLoginAuditUseCase(uow, "test"),
    )
    result = sign_in.execute(
        SignInCommand(email="admin@example.com", password="secret123", remember_me=True)
    )

    assert result.email == "admin@example.com"
    assert session_store.load_user_id() is not None

    restored_session = CurrentUserSession()
    restore = RestoreSessionUseCase(
        uow,
        restored_session,
        session_store,
        RecordLoginAuditUseCase(uow, "test"),
    )
    restored = restore.execute()

    assert restored is not None
    assert restored.email == "admin@example.com"
    assert restored.role == "admin"


def test_sign_in_without_remember_me_leaves_no_restorable_session(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)
    seed_user(uow, bundle.hasher)

    sign_in = SignInUseCase(
        uow,
        bundle.hasher,
        CurrentUserSession(),
        bundle.session_store,
        RecordLoginAuditUseCase(uow, "test"),
    )
    sign_in.execute(SignInCommand(email="admin@example.com", password="secret123"))

    assert bundle.session_store.load_user_id() is None

    restore = RestoreSessionUseCase(
        uow,
        CurrentUserSession(),
        bundle.session_store,
        RecordLoginAuditUseCase(uow, "test"),
    )
    assert restore.execute() is None


def test_sign_in_without_remember_me_clears_a_previously_remembered_session(
    uow, session_factory, tmp_path
):
    """Opting out once must not leave the earlier session restorable."""
    bundle = build_auth_bundle(session_factory, tmp_path)
    seed_user(uow, bundle.hasher)

    sign_in = SignInUseCase(
        uow,
        bundle.hasher,
        CurrentUserSession(),
        bundle.session_store,
        RecordLoginAuditUseCase(uow, "test"),
    )
    sign_in.execute(
        SignInCommand(email="admin@example.com", password="secret123", remember_me=True)
    )
    assert bundle.session_store.load_user_id() is not None

    sign_in.execute(
        SignInCommand(email="admin@example.com", password="secret123", remember_me=False)
    )
    assert bundle.session_store.load_user_id() is None


def test_restore_clears_invalid_session(uow, tmp_path):
    session_store = FileSessionStore(tmp_path / "session.json")
    session_store.save_user_id(999)

    restored_session = CurrentUserSession()
    restore = RestoreSessionUseCase(
        uow,
        restored_session,
        session_store,
        RecordLoginAuditUseCase(uow, "test"),
    )
    restored = restore.execute()

    assert restored is None
    assert session_store.load_user_id() is None

def test_restore_invalid_session_is_cleared(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)

    bundle.session_store.save_user_id(999)

    restored_session = CurrentUserSession()
    restore = RestoreSessionUseCase(
        uow,
        restored_session,
        bundle.session_store,
        bundle.audit_recorder,
    )

    restored = restore.execute()

    assert restored is None
    assert restored_session.is_authenticated() is False
    assert bundle.session_store.load_user_id() is None