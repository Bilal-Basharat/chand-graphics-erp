"""
Everything the sign-in screen, the user menu and the profile screen need:
authentication, the current user, and the remembered-credentials choice.

Unlike other view models (which hold a specific use case each), this one
holds the container: current-user reads are synchronous, in-memory session
lookups (no DB hit), not a use case in their own right.
"""
from __future__ import annotations

from PySide6.QtCore import Signal

from app.application.auth.commands import (
    ChangeEmailCommand,
    ChangePasswordCommand,
    LoginHistoryQuery,
    PasswordResetCommand,
    SignInCommand,
)
from app.application.auth.permissions import ROLE_PERMISSIONS, Permission
from app.application.auth.session import CurrentUser
from app.config.paths import SIGN_IN_PREFERENCES_PATH
from app.container import AppContainer
from app.presentation.services.credential_store import CredentialStore, RememberedCredentials
from app.presentation.viewmodels.base import BaseViewModel


class SessionViewModel(BaseViewModel):
    signedIn = Signal(object)          # SignInResult
    signedOut = Signal()
    passwordChanged = Signal()
    emailChanged = Signal(str)         # the new address
    passwordResetSent = Signal(str)    # the address it went to
    loginHistoryLoaded = Signal(list)  # list[LoginAudit]

    def __init__(
        self,
        container: AppContainer,
        credential_store: CredentialStore | None = None,
    ) -> None:
        super().__init__()
        self._container = container
        self._credentials = credential_store or CredentialStore(SIGN_IN_PREFERENCES_PATH)

    # ---------------- current user ----------------

    def current_user(self) -> CurrentUser | None:
        return self._container.current_user_session.get_user()

    def is_authenticated(self) -> bool:
        return self._container.current_user_session.is_authenticated()

    def permissions(self) -> frozenset[Permission]:
        """The signed-in user's permissions, empty when nobody is signed in."""
        user = self.current_user()
        if user is None:
            return frozenset()
        return ROLE_PERMISSIONS.get(user.role.strip().lower(), frozenset())

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions()

    # ---------------- remembered credentials ----------------

    @property
    def can_save_passwords(self) -> bool:
        """False when this machine exposes no OS credential vault."""
        return self._credentials.passwords_supported

    @property
    def can_send_email(self) -> bool:
        """False when no mail server is configured, so the screens that
        would offer to email something can say why instead of failing."""
        return self._container.email_sender().is_available

    def remembered_credentials(self) -> RememberedCredentials:
        return self._credentials.load()

    def forget_credentials(self) -> None:
        self._credentials.forget()

    # ---------------- authentication ----------------

    def sign_in(
        self,
        email: str,
        password: str,
        *,
        remember_me: bool = False,
        save_credentials: bool = False,
    ) -> None:
        use_case = self._container.sign_in_use_case()
        command = SignInCommand(email=email, password=password, remember_me=remember_me)

        def _on_success(result) -> None:
            # Only after the credentials are known good — saving them on a
            # failed attempt would autofill something that doesn't work.
            if save_credentials:
                self._credentials.remember(email, password)
            else:
                self._credentials.forget()
            self.signedIn.emit(result)

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)

    def sign_out(self) -> None:
        """Ends the session. Saved credentials are deliberately kept — the
        user asked for them to be remembered, and signing out is not a
        request to forget who normally uses this machine."""
        use_case = self._container.sign_out_use_case()
        self.run_async(lambda: use_case.execute(), on_success=lambda _: self.signedOut.emit())

    def change_password(self, current_password: str, new_password: str) -> None:
        use_case = self._container.change_password_use_case()
        command = ChangePasswordCommand(
            current_password=current_password,
            new_password=new_password,
        )

        def _on_success(_result) -> None:
            # A stored password that no longer works is worse than none:
            # it autofills silently and fails. Refresh it if we hold one.
            remembered = self._credentials.load()
            user = self.current_user()
            if remembered.has_email and user is not None and remembered.email == user.email:
                self._credentials.remember(user.email, new_password)
            self.passwordChanged.emit()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)

    def change_email(self, new_email: str, current_password: str) -> None:
        use_case = self._container.change_email_use_case()
        command = ChangeEmailCommand(new_email=new_email, current_password=current_password)

        def _on_success(email: str) -> None:
            # The remembered email is what prefills the sign-in form, so
            # leaving the old one there would autofill an address that no
            # longer signs in.
            remembered = self._credentials.load()
            if remembered.has_email:
                self._credentials.remember(email, current_password)
            self.emailChanged.emit(email)

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)

    def request_password_reset(self, email: str) -> None:
        """Email a temporary password to an account that has lost its own."""
        use_case = self._container.request_password_reset_use_case()
        command = PasswordResetCommand(email=email)

        def _on_success(result) -> None:
            # Whatever this machine had saved for that address is now dead;
            # keeping it would silently prefill a password that fails.
            remembered = self._credentials.load()
            if remembered.email == result.email:
                self._credentials.forget()
            self.passwordResetSent.emit(result.email)

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)

    # ---------------- audit ----------------

    def load_login_history(self, limit: int = 25) -> None:
        """Recent sign-in activity for the current user.

        Requires VIEW_REPORTS, which the staff role does not hold — check
        `has_permission` before calling, or the view model will surface a
        permission error the user can do nothing about.
        """
        user = self.current_user()
        if user is None:
            self.loginHistoryLoaded.emit([])
            return

        use_case = self._container.login_history_use_case()
        query = LoginHistoryQuery(user_id=user.user_id, limit=limit)
        self.run_async(lambda: use_case.execute(query), on_success=self.loginHistoryLoaded.emit)
