"""Whether this copy of the application can send email at all.

`is_available` is what the sign-in screen asks before it offers "Forgot
password", so getting it wrong shows up as one of two bad screens: a
dialog that opens, takes an address, promises an email and then fails —
or the message box saying email is off on a build that could have sent
it perfectly well.
"""
from __future__ import annotations

import pytest

from app.config.settings import SmtpSettings
from app.infrastructure.notifications import smtp_email_sender
from app.infrastructure.notifications.smtp_email_sender import SmtpEmailSender


class FakeVault:
    """Stands in for the OS credential vault, which a test machine may or
    may not have and which must not be written to either way."""

    def __init__(self, stored: dict[str, str] | None = None) -> None:
        self._stored = stored or {}

    def get(self, key: str) -> str | None:
        return self._stored.get(key)


def _settings(**overrides) -> SmtpSettings:
    values = {
        "host": "smtp.example.com",
        "port": 587,
        "username": "shop@example.com",
        "sender": "shop@example.com",
        "use_tls": True,
    }
    return SmtpSettings(**{**values, **overrides})


@pytest.fixture()
def unprovisioned(monkeypatch):
    """A build packaged with no mail account of its own."""
    monkeypatch.setattr(smtp_email_sender, "provisioned_secret", lambda _key: None)


@pytest.fixture()
def provisioned(monkeypatch):
    """A build packaged the way a release is."""
    monkeypatch.setattr(smtp_email_sender, "provisioned_secret", lambda _key: "from-the-build")


# ------------------------------------------------------- availability


def test_a_build_with_no_mail_server_cannot_send(unprovisioned):
    sender = SmtpEmailSender(_settings(host="", sender=""), FakeVault())

    assert not sender.is_available


def test_a_mail_server_with_no_password_anywhere_cannot_send(unprovisioned):
    """The gap this closes: settings alone used to be enough to say yes,
    so the dialog opened and the send failed after the promise."""
    sender = SmtpEmailSender(_settings(), FakeVault())

    assert not sender.is_available


def test_the_password_the_build_carries_is_enough(provisioned):
    """No vault entry, no settings.json, nothing done on the machine —
    which is every ordinary installation."""
    sender = SmtpEmailSender(_settings(), FakeVault())

    assert sender.is_available


def test_a_password_saved_on_the_machine_is_enough(unprovisioned):
    sender = SmtpEmailSender(_settings(), FakeVault({"smtp-password": "on-this-machine"}))

    assert sender.is_available


def test_a_server_wanting_no_account_needs_no_password(unprovisioned):
    sender = SmtpEmailSender(_settings(username=""), FakeVault())

    assert sender.is_available


# ---------------------------------------------------------- precedence


def test_the_machines_own_password_wins_over_the_builds(provisioned):
    """A machine that was given its own mail account keeps using it, so
    an installation set up before this build stays set up."""
    sender = SmtpEmailSender(_settings(), FakeVault({"smtp-password": "on-this-machine"}))

    assert sender._password() == "on-this-machine"


def test_the_builds_password_is_used_when_the_machine_has_none(provisioned):
    sender = SmtpEmailSender(_settings(), FakeVault())

    assert sender._password() == "from-the-build"


# ------------------------------------------------------------ refusal


def test_sending_without_a_mail_server_says_so_without_naming_a_command(unprovisioned):
    """This text reaches a shop counter, so it must not send anyone to a
    developer CLI or a JSON file."""
    from app.application.exceptions import EmailDeliveryError
    from app.domain.notifications.email_sender import EmailMessage

    sender = SmtpEmailSender(_settings(host="", sender=""), FakeVault())

    with pytest.raises(EmailDeliveryError) as raised:
        sender.send(EmailMessage(to="someone@example.com", subject="x", body="y"))

    assert "scripts" not in str(raised.value)
    assert "settings.json" not in str(raised.value)
