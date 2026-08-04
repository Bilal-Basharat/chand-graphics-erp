"""
Forgotten-password recovery.

This emails a new temporary password rather than a reset link. A link
needs a token store, an expiry sweep and somewhere for the user to click
it — all of which assume a web app and a server. This is a desktop ERP on
a shop's own machine: the shortest honest path is to set a password only
the account's mailbox has seen, and let the person change it from My
profile once they are back in, which they can already do.

The consequence is stated plainly to the user: the old password stops
working the moment this succeeds.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.application.auth.commands import PasswordResetCommand, RecordLoginAuditCommand
from app.application.auth.email_address import clean_email
from app.application.auth.exceptions import (
    InactiveAccountError,
    InvalidCredentialsError,
    LoginThrottledError,
)
from app.application.auth.login_audit_use_cases import RecordLoginAuditUseCase
from app.application.use_cases.base import UseCase
from app.domain.enums.login_event_type import LoginEventType
from app.domain.notifications.email_sender import EmailMessage, EmailSender
from app.domain.security.password_hasher import PasswordHasher
from app.domain.uow import UnitOfWork

logger = logging.getLogger(__name__)

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
"""No O/0 or I/l/1: this password is read off a screen and typed by hand,
and a character you cannot tell apart is a failed sign-in."""

_LENGTH = 12

_MAX_RESETS = 3
_WINDOW_MINUTES = 30
"""Without a ceiling, anyone at the sign-in screen could reset the shop
owner's password on repeat — filling their inbox and locking them out of
the password they know. Three in half an hour covers mistyping the
address; a fourth is not someone who forgot their password."""


@dataclass(slots=True)
class PasswordResetResult:
    email: str
    """Echoed back so the screen can name the address it went to, which is
    the one thing the user needs to check if nothing arrives."""


def generate_temporary_password() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))


class RequestPasswordResetUseCase(UseCase[PasswordResetCommand, PasswordResetResult]):
    """
    Email a new temporary password to an account that has lost its own.

    Runs with nobody signed in — it is reached from the sign-in screen.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        password_hasher: PasswordHasher,
        email_sender: EmailSender,
        record_login_audit_use_case: RecordLoginAuditUseCase,
        app_name: str,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.email_sender = email_sender
        self.record_login_audit_use_case = record_login_audit_use_case
        self.app_name = app_name

    def execute(self, request: PasswordResetCommand) -> PasswordResetResult:
        # Cleaned, not validated: this address is being looked up, not set.
        # See email_address.clean_email.
        email = clean_email(request.email)

        with self.uow as uow:
            users = self.require(uow.users, "users")
            audits = self.require(uow.login_audits, "login_audits")

            user = users.get_by_email(email)
            # Named plainly rather than answered with a deliberately vague
            # "if that address exists we've sent something". This is a
            # single shop's internal tool where the staff addresses are
            # already known to each other, and a user who mistyped their
            # own address needs to be told that, not reassured.
            if user is None:
                raise InvalidCredentialsError(f"No account is registered to '{email}'.")

            if not user.is_active:
                raise InactiveAccountError(
                    "That account is inactive, so its password cannot be reset."
                )

            since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                minutes=_WINDOW_MINUTES
            )
            if audits.count_recent_events(email, LoginEventType.PASSWORD_RESET, since) >= _MAX_RESETS:
                raise LoginThrottledError(
                    "This account's password has been reset several times just now. "
                    f"Wait {_WINDOW_MINUTES} minutes before trying again."
                )

            temporary_password = generate_temporary_password()

            # Sent before the new password is saved, so a mail server that
            # refuses the message leaves the old password working. The
            # reverse order locks the user out of an account whose new
            # password never reached them.
            self.email_sender.send(
                EmailMessage(
                    to=user.email,
                    subject=f"{self.app_name} — your temporary password",
                    body=_body(self.app_name, user.full_name, temporary_password),
                )
            )

            user.password_hash = self.password_hasher.hash(temporary_password)
            users.update(user)
            user_id = user.id

        # Outside the transaction on purpose. The audit use case opens a
        # connection of its own, and SQLite refuses a second writer while
        # this one still holds the write lock — the insert failed with
        # "database is locked", was swallowed by the guard below, and took
        # the reset throttle down with it, since the throttle counts these
        # very rows.
        self._record(email, user_id)
        return PasswordResetResult(email=email)

    def _record(self, email: str, user_id: int | None) -> None:
        try:
            self.record_login_audit_use_case.execute(
                RecordLoginAuditCommand(
                    email=email,
                    user_id=user_id,
                    event_type=LoginEventType.PASSWORD_RESET,
                    success=True,
                    message="Temporary password emailed",
                )
            )
        except Exception:
            # The password has already been changed and sent. Losing the
            # audit line is worth reporting, not worth failing over.
            logger.exception("Failed to write password-reset audit record")


def _body(app_name: str, full_name: str, temporary_password: str) -> str:
    return (
        f"Hello {full_name},\n\n"
        f"A password reset was requested for your {app_name} account.\n\n"
        f"Your temporary password is:\n\n"
        f"    {temporary_password}\n\n"
        "Sign in with it, then change it from My profile → Change password.\n"
        "Your previous password no longer works.\n\n"
        "If you did not ask for this, sign in and change your password now.\n"
    )
