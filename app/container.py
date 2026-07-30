from __future__ import annotations

from dataclasses import dataclass, field

from app.application.auth.session import CurrentUserSession
from app.domain.security.password_hasher import PasswordHasher
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from app.infrastructure.uow import SqlAlchemyUnitOfWork
from app.application.auth.initial_admin import EnsureInitialAdminUserUseCase
from app.config.settings import AppSettings

from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.auth.commands import RecordLoginAuditCommand
from app.application.auth.login_audit_use_cases import RecordLoginAuditUseCase, ListLoginHistoryUseCase
from app.application.auth.session_store import SessionStore
from app.domain.enums.login_event_type import LoginEventType
from app.infrastructure.auth import FileSessionStore
from app.config.settings import APP_VERSION, SESSION_FILE_PATH
from app.application.auth.throttling import LoginThrottleService

@dataclass(slots=True)
class AppContainer:
    """
    Simple composition root for the application.
    """
    settings: AppSettings = field(default_factory=AppSettings.from_env)
    current_user_session: CurrentUserSession = field(default_factory=CurrentUserSession)
    password_hasher: PasswordHasher = field(default_factory=BcryptPasswordHasher)
    session_store: SessionStore = field(default_factory=lambda: FileSessionStore(SESSION_FILE_PATH))

    def create_uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork()

    def sign_in_use_case(self):
        from app.application.auth.use_cases import SignInUseCase
        return SignInUseCase(self.create_uow(), self.password_hasher, self.current_user_session, self.session_store, self.record_login_audit_use_case(), self.login_throttle_service())

    def authorization_service(self) -> AuthorizationService:
        return AuthorizationService(self.current_user_session)

    def sign_out_use_case(self):
        from app.application.auth.use_cases import SignOutUseCase
        return SignOutUseCase(self.current_user_session, self.session_store, self.record_login_audit_use_case(),)

    def restore_session_use_case(self):
        from app.application.auth.use_cases import RestoreSessionUseCase
        return RestoreSessionUseCase(
            self.create_uow(),
            self.current_user_session,
            self.session_store,
            self.record_login_audit_use_case(),
        )

    def current_user_use_case(self):
        from app.application.auth.use_cases import GetCurrentUserUseCase
        return GetCurrentUserUseCase(self.current_user_session)

    def change_password_use_case(self):
        from app.application.auth.use_cases import ChangePasswordUseCase
        return ChangePasswordUseCase(self.create_uow(), self.password_hasher, self.current_user_session)

    def ensure_initial_admin_use_case(self) -> EnsureInitialAdminUserUseCase:
        return EnsureInitialAdminUserUseCase(self.create_uow(), self.password_hasher)

    def create_initializer(self):
        from app.application.startup.application_initializer import ApplicationInitializer
        return ApplicationInitializer(
        ensure_initial_admin_use_case=self.ensure_initial_admin_use_case(),
        restore_session_use_case=self.restore_session_use_case(),
        settings=self.settings,
        )

    def record_login_audit_use_case(self) -> RecordLoginAuditUseCase:
        return RecordLoginAuditUseCase(self.create_uow(), APP_VERSION)

    def login_history_use_case(self):
        from app.application.auth.login_audit_use_cases import ListLoginHistoryUseCase
        return ListLoginHistoryUseCase(
            self.create_uow(),
            self.current_user_session,
            self.authorization_service(),
        )

    def login_throttle_service(self) -> LoginThrottleService:
        return LoginThrottleService(self.create_uow(), self.settings)