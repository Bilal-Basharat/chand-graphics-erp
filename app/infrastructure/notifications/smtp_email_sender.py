from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage as MimeMessage

from app.application.exceptions import EmailDeliveryError
from app.config.settings import SmtpSettings
from app.domain.notifications.email_sender import EmailMessage, EmailSender

logger = logging.getLogger(__name__)

_IMPLICIT_TLS_PORT = 465
"""Providers offer either 587 with STARTTLS or 465 with TLS from the
start. The port is what tells the two apart."""

_TIMEOUT_SECONDS = 20
"""A person is watching a spinner while this runs. Long enough for a slow
provider, short enough that a black hole reports back rather than hangs."""


class SmtpEmailSender(EmailSender):
    """Sends mail through the server configured in the environment."""

    def __init__(self, settings: SmtpSettings) -> None:
        self._settings = settings

    @property
    def is_available(self) -> bool:
        return self._settings.is_configured

    def send(self, message: EmailMessage) -> None:
        if not self.is_available:
            raise EmailDeliveryError(
                "No mail server is configured, so this app cannot send email. "
                "Ask whoever set it up to fill in the SMTP settings."
            )

        try:
            with self._connect() as server:
                if self._settings.username:
                    server.login(self._settings.username, self._settings.password)
                server.send_message(_build(message, self._settings.sender))
        except (OSError, smtplib.SMTPException) as exc:
            # Logged in full, reported in short: the SMTP failure text names
            # the server and sometimes the credentials, neither of which
            # belongs in a dialog on a shop counter.
            logger.exception("Failed to send email to %s", message.to)
            raise EmailDeliveryError(
                "The email could not be sent. Check the internet connection "
                "and the mail server settings, then try again."
            ) from exc

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
