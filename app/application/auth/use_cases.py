from __future__ import annotations

from dataclasses import dataclass

from app.application.auth.commands import ChangePasswordCommand, SignInCommand
from app.application.auth.exceptions import (InactiveAccountError, InvalidCredentialsError, LoginThrottledError)
from app.application.auth.session import CurrentUser, CurrentUserSession
from app.application.use_cases.base import UseCase
from app.domain.entities.user import User
from app.domain.repositories.user_repository import UserRepository
from app.domain.security.password_hasher import PasswordHasher
from app.domain.uow import UnitOfWork
from app.application.auth.session_store import SessionStore

import logging
from app.application.auth.commands import RecordLoginAuditCommand
from app.application.auth.login_audit_use_cases import RecordLoginAuditUseCase
from app.domain.enums.login_event_type import LoginEventType



from app.application.auth.throttling import LoginThrottleService
from app.domain.enums.login_event_type import LoginEventType

logger = logging.getLogger(__name__)


def _safe_record_audit(
    recorder: RecordLoginAuditUseCase,
    command: RecordLoginAuditCommand,
) -> None:
    try:
        recorder.execute(command)
    except Exception:
        logger.exception("Failed to write login audit record")

@dataclass(slots=True)
class SignInResult:
    user_id: int
    email: str
    full_name: str
    role: str


class SignInUseCase(UseCase[SignInCommand, SignInResult]):
    """
    Authenticate a user by email/password and store them in the current session.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        password_hasher: PasswordHasher,
        current_user_session: CurrentUserSession,
        session_store: SessionStore,
        record_login_audit_use_case: RecordLoginAuditUseCase,
        login_throttle_service: LoginThrottleService | None = None,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.current_user_session = current_user_session
        self.session_store = session_store
        self.record_login_audit_use_case = record_login_audit_use_case
        self.login_throttle_service = login_throttle_service

    def execute(self, request: SignInCommand) -> SignInResult:
        email = request.email.strip().lower()
        password = request.password

        if not email or not password:
            _safe_record_audit(
            self.record_login_audit_use_case,
            RecordLoginAuditCommand(
                email=email or request.email.strip(),
                event_type=LoginEventType.SIGN_IN_FAILURE,
                success=False,
                message="Email and password are required",
                ),
            )
            raise InvalidCredentialsError("Email and password are required")

        try:
            if self.login_throttle_service is not None:
                self.login_throttle_service.require_not_throttled(email)
        except LoginThrottledError as exc:
            _safe_record_audit(
                self.record_login_audit_use_case,
                RecordLoginAuditCommand(
                    email=email,
                    event_type=LoginEventType.SIGN_IN_FAILURE,
                    success=False,
                    message=str(exc),
                ),
            )
            raise

        with self.uow as uow:
            users = self.require(uow.users, "users")

            user = users.get_by_email(email)
            if user is None:
                _safe_record_audit(
                self.record_login_audit_use_case,
                RecordLoginAuditCommand(
                    email=email,
                    event_type=LoginEventType.SIGN_IN_FAILURE,
                    success=False,
                    message="Invalid email or password",
                    ),
                )
                raise InvalidCredentialsError("Invalid email or password")

            if not user.is_active:
                _safe_record_audit(
                self.record_login_audit_use_case,
                RecordLoginAuditCommand(
                    email=email,
                    user_id=user.id,
                    event_type=LoginEventType.SIGN_IN_FAILURE,
                    success=False,
                    message="Account is inactive",
                    ),
                )
                raise InactiveAccountError("This account is inactive")

            if not self.password_hasher.verify(password, user.password_hash):
                _safe_record_audit(
                self.record_login_audit_use_case,
                RecordLoginAuditCommand(
                    email=email,
                    user_id=user.id,
                    event_type=LoginEventType.SIGN_IN_FAILURE,
                    success=False,
                    message="Invalid email or password",
                    ),
                )
                raise InvalidCredentialsError("Invalid email or password")

            self.current_user_session.set_user(user)
            self.session_store.save_user_id(user.id)  # type: ignore[arg-type]

            _safe_record_audit(
            self.record_login_audit_use_case,
            RecordLoginAuditCommand(
                email=email,
                user_id=user.id,
                event_type=LoginEventType.SIGN_IN_SUCCESS,
                success=True,
                message="Signed in successfully",
                ),
            )

            return SignInResult(
                user_id=user.id,  # type: ignore[arg-type]
                email=user.email,
                full_name=user.full_name,
                role=user.role,
            )


class SignOutUseCase(UseCase[None, None]):
    """
    Clear the current signed-in user.
    """

    def __init__(self, current_user_session: CurrentUserSession, session_store: SessionStore, record_login_audit_use_case: RecordLoginAuditUseCase,) -> None:
        self.current_user_session = current_user_session
        self.session_store = session_store
        self.record_login_audit_use_case = record_login_audit_use_case
        
        

    def execute(self, request: None = None) -> None:

        current_user = self.current_user_session.require_user()

        _safe_record_audit(
        self.record_login_audit_use_case,
        RecordLoginAuditCommand(
            email=current_user.email,
            user_id=current_user.user_id,
            event_type=LoginEventType.SIGN_OUT,
            success=True,
            message="Signed out",
            ),
        )
        self.current_user_session.clear()
        self.session_store.clear()


class GetCurrentUserUseCase(UseCase[None, CurrentUser | None]):
    """
    Return the current signed-in user, or None if nobody is signed in.
    """

    def __init__(self, current_user_session: CurrentUserSession) -> None:
        self.current_user_session = current_user_session

    def execute(self, request: None = None) -> CurrentUser | None:
        return self.current_user_session.get_user()


class ChangePasswordUseCase(UseCase[ChangePasswordCommand, None]):
    """
    Change password for the currently signed-in user.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        password_hasher: PasswordHasher,
        current_user_session: CurrentUserSession,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.current_user_session = current_user_session

    def execute(self, request: ChangePasswordCommand) -> None:
        current_user = self.current_user_session.require_user()

        if not request.current_password or not request.new_password:
            raise ValueError("Both current and new passwords are required")

        with self.uow as uow:
            users = self.require(uow.users, "users")
            user = users.get_by_id(current_user.user_id)

            if user is None:
                raise InvalidCredentialsError("Current user no longer exists")

            if not self.password_hasher.verify(request.current_password, user.password_hash):
                raise InvalidCredentialsError("Current password is incorrect")

            user.password_hash = self.password_hasher.hash(request.new_password)
            users.update(user)


class RestoreSessionUseCase(UseCase[None, CurrentUser | None]):
    """
    Restore the remembered signed-in user on application startup.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession,
        session_store: SessionStore,
        record_login_audit_use_case: RecordLoginAuditUseCase,
    ) -> None:
        self.uow = uow
        self.current_user_session = current_user_session
        self.session_store = session_store
        self.record_login_audit_use_case = record_login_audit_use_case

    def execute(self, request: None = None) -> CurrentUser | None:
        user_id = self.session_store.load_user_id()
        if user_id is None:
            self.current_user_session.clear()
            return None

        with self.uow as uow:
            users = self.require(uow.users, "users")
            user = users.get_by_id(user_id)

            if user is None or not user.is_active:
                self.current_user_session.clear()
                self.session_store.clear()
                return None

            self.current_user_session.set_user(user)

            _safe_record_audit(
            self.record_login_audit_use_case,
            RecordLoginAuditCommand(
                email=user.email,
                user_id=user.id,
                event_type=LoginEventType.SESSION_RESTORED,
                success=True,
                message="Session restored on startup",
                ),
            )
            
            return self.current_user_session.require_user()