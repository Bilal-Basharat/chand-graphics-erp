from __future__ import annotations

import pytest

from app.application.auth.commands import SignInCommand
from app.application.auth.exceptions import LoginThrottledError
from app.application.auth.session import CurrentUserSession
from app.application.auth.throttling import LoginThrottleService
from app.application.auth.use_cases import SignInUseCase
from app.config.settings import AppSettings
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher

from ._helpers import build_auth_bundle, seed_user


def test_sign_in_gets_throttled_after_too_many_recent_failures(uow, session_factory, tmp_path):
    bundle = build_auth_bundle(session_factory, tmp_path)
    seed_user(uow, bundle.hasher)

    settings = AppSettings(
        app_name="Test App",
        company_name="Test Company",
        app_version="test",
        developed_by="Test Devs",
        initial_admin_email="admin@localhost",
        initial_admin_password="admin123",
        initial_admin_full_name="Administrator",
        initial_admin_role="admin",
        max_login_attempts=1,
        login_lockout_minutes=15,
    )

    throttle_service = LoginThrottleService(uow, settings)

    use_case = SignInUseCase(
        uow,
        bundle.hasher,
        bundle.current_user_session,
        bundle.session_store,
        bundle.audit_recorder,
        throttle_service,
    )

    with pytest.raises(Exception):
        use_case.execute(SignInCommand(email="admin@example.com", password="wrong-password"))

    with pytest.raises(LoginThrottledError):
        use_case.execute(SignInCommand(email="admin@example.com", password="secret123"))