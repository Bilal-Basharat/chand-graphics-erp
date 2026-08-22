from __future__ import annotations

from dataclasses import dataclass

from app.application.auth.commands import EnsureInitialAdminUserCommand
from app.application.auth.initial_admin import EnsureInitialAdminUserUseCase
from app.application.auth.use_cases import RestoreSessionUseCase
from app.application.use_cases.catalogue import EnsureDefaultCategoryUseCase
from app.config import constants


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
    ensure_default_category_use_case: EnsureDefaultCategoryUseCase
    restore_session_use_case: RestoreSessionUseCase

    def initialize(self) -> None:
        self._ensure_initial_admin()
        self._ensure_default_category()
        self._restore_session()

    def _ensure_initial_admin(self) -> None:
        """Give a brand-new database an account that can sign in.

        The credentials come from application constants rather than from
        configuration: they are how a fresh installation is opened for
        the first time, not something a customer is asked to set up
        before the app will start. The use case only acts on an empty
        users table, so once a real administrator exists — or this one's
        password is changed — nothing here touches it again.
        """
        self.ensure_initial_admin_use_case.execute(
            EnsureInitialAdminUserCommand(
                email=constants.DEFAULT_ADMIN_EMAIL,
                password=constants.DEFAULT_ADMIN_PASSWORD,
                full_name=constants.DEFAULT_ADMIN_FULL_NAME,
                role=constants.DEFAULT_ADMIN_ROLE,
            )
        )

    def _ensure_default_category(self) -> None:
        """Give the catalogue the one shelf that needs no decision.

        Every product is filed somewhere, so there has to be somewhere to
        file one before the shopkeeper has made any shelves of their own.
        Like the initial administrator, it is created once and left alone
        after that.
        """
        self.ensure_default_category_use_case.execute()

    def _restore_session(self) -> None:
        self.restore_session_use_case.execute()
