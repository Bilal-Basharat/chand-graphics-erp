from __future__ import annotations

from dataclasses import dataclass

from app.application.auth.commands import EnsureInitialAdminUserCommand
from app.application.auth.initial_admin import EnsureInitialAdminUserUseCase
from app.config.settings import AppSettings
from app.application.auth.use_cases import RestoreSessionUseCase

@dataclass(slots=True)
class ApplicationInitializer:
    """
    Runs one-time and startup tasks for the desktop application.

    Keep bootstrap.py thin and stable:
    - initialize database
    - create container
    - call initializer.initialize()
    - launch UI
    """

    ensure_initial_admin_use_case: EnsureInitialAdminUserUseCase
    restore_session_use_case: RestoreSessionUseCase
    settings: AppSettings

    def initialize(self) -> None:
        self._ensure_initial_admin()
        self._restore_session()

    def _ensure_initial_admin(self) -> None:
        self.ensure_initial_admin_use_case.execute(
            EnsureInitialAdminUserCommand(
                email=self.settings.initial_admin_email,
                password=self.settings.initial_admin_password,
                full_name=self.settings.initial_admin_full_name,
                role=self.settings.initial_admin_role,
            )
        )

    def _restore_session(self) -> None:
        self.restore_session_use_case.execute()