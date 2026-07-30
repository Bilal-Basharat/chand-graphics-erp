from __future__ import annotations

from app.application.auth.commands import EnsureInitialAdminUserCommand
from app.application.auth.initial_admin import EnsureInitialAdminUserUseCase
from app.domain.entities.user import User
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher


def test_initial_admin_is_created_when_users_table_is_empty(uow):
    hasher = BcryptPasswordHasher()
    use_case = EnsureInitialAdminUserUseCase(uow, hasher)

    user = use_case.execute(
        EnsureInitialAdminUserCommand(
            email="admin@example.com",
            password="secret123",
            full_name="System Admin",
            role="admin",
        )
    )

    assert user is not None
    assert user.id is not None
    assert user.email == "admin@example.com"
    assert user.role == "admin"
    assert user.is_active is True

    with uow as tx:
        users = tx.users
        assert users is not None

        saved = users.get_by_email("admin@example.com")
        assert saved is not None
        assert hasher.verify("secret123", saved.password_hash) is True


def test_initial_admin_is_not_created_if_any_user_already_exists(uow):
    hasher = BcryptPasswordHasher()

    with uow as tx:
        users = tx.users
        assert users is not None

        users.add(
            User(
                email="existing@example.com",
                password_hash=hasher.hash("existing123"),
                full_name="Existing User",
                role="admin",
                is_active=True,
            )
        )

    use_case = EnsureInitialAdminUserUseCase(uow, hasher)
    result = use_case.execute(
        EnsureInitialAdminUserCommand(
            email="admin@example.com",
            password="secret123",
            full_name="System Admin",
            role="admin",
        )
    )

    assert result is None