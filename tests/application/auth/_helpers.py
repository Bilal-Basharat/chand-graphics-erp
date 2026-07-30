from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.application.auth.login_audit_use_cases import RecordLoginAuditUseCase
from app.application.auth.session import CurrentUserSession
from app.domain.entities.user import User
from app.infrastructure.auth.file_session_store import FileSessionStore
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from app.infrastructure.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork


@dataclass(slots=True)
class AuthBundle:
    hasher: BcryptPasswordHasher
    current_user_session: CurrentUserSession
    session_store: FileSessionStore
    audit_recorder: RecordLoginAuditUseCase


def build_auth_bundle(
    session_factory: Callable[[], Session],
    tmp_path: Path,
    app_version: str = "test",
) -> AuthBundle:
    return AuthBundle(
        hasher=BcryptPasswordHasher(),
        current_user_session=CurrentUserSession(),
        session_store=FileSessionStore(tmp_path / "session.json"),
        audit_recorder=RecordLoginAuditUseCase(
            SqlAlchemyUnitOfWork(session_factory=session_factory),
            app_version,
        ),
    )


def seed_user(
    uow: SqlAlchemyUnitOfWork,
    hasher: BcryptPasswordHasher,
    *,
    email: str = "admin@example.com",
    password: str = "secret123",
    full_name: str = "Admin User",
    role: str = "admin",
    is_active: bool = True,
) -> User:
    with uow as tx:
        users = tx.users
        assert users is not None

        user = User(
            email=email,
            password_hash=hasher.hash(password),
            full_name=full_name,
            role=role,
            is_active=is_active,
        )
        return users.add(user)