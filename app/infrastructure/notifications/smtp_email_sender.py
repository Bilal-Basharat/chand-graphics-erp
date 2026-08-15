from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage as MimeMessage

from app.application.exceptions import EmailDeliveryError
from app.config.provisioning import provisioned_secret
from app.config.settings import SmtpSettings
from app.domain.notifications.email_sender import EmailMessage, EmailSender
from app.infrastructure.security.secret_vault import SMTP_PASSWORD_KEY, SecretVault

logger = logging.getLogger(__name__)

_IMPLICIT_TLS_PORT = 465
"""Providers offer either 587 with STARTTLS or 465 with TLS from the
start. The port is what tells the two apart."""

_TIMEOUT_SECONDS = 20
"""A person is watching a spinner while this runs. Long enough for a slow
provider, short enough that a black hole reports back rather than hangs."""

_CANNOT_SEND = (
    "This copy of the app is not set up to send email, so it cannot send "
    "this message. Please contact support."
)
"""Said the same way whether the server or the password is the part that
is missing. Both mean a build that was packaged without its mail account,
neither is anything the person reading it can act on differently, and the
log line says which. `is_available` normally catches this at the button;
these raises are the guard for the gap between that check and the send."""


class SmtpEmailSender(EmailSender):
    """Sends mail through the server this installation is configured for.

    The server's address, port and account come from configuration; its
    password is fetched at the moment it is needed, never held. That
    keeps the one secret involved out of every configuration object, log
    line and crash dump this application produces.
    """

    def __init__(self, settings: SmtpSettings, vault: SecretVault | None = None) -> None:
        self._settings = settings
        self._vault = vault or SecretVault()

    @property
    def is_available(self) -> bool:
        """Whether a message sent right now stands a chance.

        Deliberately more than "is a server configured": an account this
        cannot authenticate as is a "Forgot password" dialog that opens,
        takes an address, and fails on submit — after the user has been
        promised an email. Better to know at the button.

        The username test mirrors `send()`'s own: a server that wants no
        account needs no password either.
        """
        if not self._settings.is_configured:
            return False
        return not self._settings.username or self._stored_password() is not None

    def send(self, message: EmailMessage) -> None:
        if not self._settings.is_configured:
            logger.error("No mail server is configured; cannot send to %s", message.to)
            raise EmailDeliveryError(_CANNOT_SEND)

        try:
            with self._connect() as server:
                if self._settings.username:
                    server.login(self._settings.username, self._password())
                server.send_message(_build(message, self._settings.sender))
        except (OSError, smtplib.SMTPException) as exc:
            # Logged in full, reported in short: the SMTP failure text names
            # the server and sometimes the credentials, neither of which
            # belongs in a dialog on a shop counter.
            logger.exception("Failed to send email to %s", message.to)
            raise EmailDeliveryError(
                "The email could not be sent. Check this computer's internet "
                "connection, then try again."
            ) from exc

    def _stored_password(self) -> str | None:
        """The mail account's password, or `None` if this copy has none.

        The OS credential vault first, so a machine that was given its own
        mail account keeps using it; what the build was provisioned with
        second, which is what every ordinary installation runs on.
        """
        return self._vault.get(SMTP_PASSWORD_KEY) or provisioned_secret(SMTP_PASSWORD_KEY)

    def _password(self) -> str:
        """As above, for the moment one is actually required.

        Refuses rather than authenticating with an empty string and
        reporting the provider's answer, which would send whoever reads
        the log looking at the mail server rather than at the build.
        """
        password = self._stored_password()
        if password:
            return password

        logger.error("No password is stored for the mail account '%s'", self._settings.username)
        raise EmailDeliveryError(_CANNOT_SEND)

    def _connect(self) -> smtplib.SMTP:
        """Open the connection the port calls for.

        Port 465 is TLS from the first byte, so STARTTLS on it fails before
        anything is sent — the difference between the two common provider
        setups, and not something to leave a shop owner to work out from a
        protocol error.
        """
        if self._settings.use_tls and self._settings.port == _IMPLICIT_TLS_PORT:
            return smtplib.SMTP_SSL(
                self._settings.host, self._settings.port, timeout=_TIMEOUT_SECONDS
            )

        server = smtplib.SMTP(
            self._settings.host, self._settings.port, timeout=_TIMEOUT_SECONDS
        )
        if self._settings.use_tls:
            server.starttls()
        return server


def _build(message: EmailMessage, sender: str) -> MimeMessage:
    """Assemble the MIME message.

    `set_content` rather than `set_payload`: it picks the transfer
    encoding to match the text, so a body that is plain ASCII — which the
    one message this app sends is, apart from an arrow — stays readable
    on the wire instead of being base64'd wholesale.
    """
    built = MimeMessage()
    built["From"] = sender
    built["To"] = message.to
    built["Subject"] = message.subject
    built.set_content(message.body)
    return built
