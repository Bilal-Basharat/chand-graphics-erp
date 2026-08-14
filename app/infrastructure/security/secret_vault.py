"""
The operating system's credential vault, as this application uses it.

Every secret this application keeps goes here and nowhere else: the
remembered sign-in password, and the mail server's password. The vault
(Windows Credential Manager, via `keyring`) encrypts entries per user
account. Writing a secret into our own JSON — or "encrypting" it with a
key shipped in the same build — would be security theatre, and putting
one in a `.env` bundled into the installer would be worse: it would ship
the same password to every customer in a file they can open.

If no vault backend is available, storage degrades to "off" rather than
falling back to plaintext. `is_available` reports that, so a caller can
say so plainly instead of silently losing what it was handed.
"""
from __future__ import annotations

import logging

from app.config.constants import KEYRING_SERVICE

logger = logging.getLogger(__name__)

SMTP_PASSWORD_KEY = "smtp-password"
"""The entry the outgoing mail password is filed under. Sign-in
passwords are filed under the email address they belong to, so a name
that is not an address cannot collide with one."""

try:  # pragma: no cover - depends on the machine's available backends
    import keyring
    from keyring.errors import KeyringError

    _keyring_imported = True
except ImportError:  # pragma: no cover
    keyring = None  # type: ignore[assignment]
    KeyringError = Exception  # type: ignore[assignment, misc]
    _keyring_imported = False


def _backend_usable() -> bool:
    """True when a real, non-failing backend is present.

    `keyring` always imports; whether it has a usable backend depends on
    the machine, and the "fail" backend raises on every call.
    """
    if not _keyring_imported:
        return False
    try:
        backend = keyring.get_keyring()
    except Exception:  # pragma: no cover - defensive
        return False
    return "fail" not in type(backend).__module__.lower()


class SecretVault:
    """Reads and writes this application's entries in the OS vault."""

    def __init__(self, service: str = KEYRING_SERVICE) -> None:
        self._service = service
        self._available = _backend_usable()

    @property
    def is_available(self) -> bool:
        """False when the OS has no credential vault we can use."""
        return self._available

    def get(self, key: str) -> str | None:
        if not self._available:
            return None
        try:
            return keyring.get_password(self._service, key)
        except KeyringError:
            logger.exception("Could not read '%s' from the credential vault", key)
            return None

    def set(self, key: str, secret: str) -> bool:
        """Store a secret. Returns whether it was actually stored."""
        if not self._available:
            return False
        try:
            keyring.set_password(self._service, key, secret)
        except KeyringError:
            logger.exception("Could not save '%s' to the credential vault", key)
            return False
        return True

    def delete(self, key: str) -> None:
        if not self._available:
            return
        try:
            keyring.delete_password(self._service, key)
        except KeyringError:
            # Nothing stored under that name — nothing to undo.
            logger.debug("No vault entry to remove for %s", key)
