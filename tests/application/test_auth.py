from __future__ import annotations

import pytest

from app.application.auth.commands import SignInCommand
from app.application.auth.exceptions import InvalidCredentialsError
from app.application.auth.use_cases import SignInUseCase, SignOutUseCase
from app.application.use_cases.master_data import CreateCompanySettingsUseCase
from app.application.use_cases.master_data import CreatePaymentMethodUseCase
from app.application.dto.commands import CreatePaymentMethodCommand
from app.domain.entities.user import User
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher


def test_sign_in_success(uow):
    hasher = BcryptPasswordHasher()

    with uow as tx:
        users = tx.users
        assert users is not None

        user = User(
            email="admin@example.com",
            password_hash=hasher.hash("secret123"),
            full_name="Admin User",
            role="admin",
            is_active=True,
        )
        users.add(user)

    session = uow  # not used here directly; only needed as a factory object
    # Use a fresh UoW instance for the sign in flow in real app code