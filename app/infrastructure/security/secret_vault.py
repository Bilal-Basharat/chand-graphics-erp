"""
The operating system's credential vault, as this application uses it.

Every secret belonging to a *machine* goes here and nowhere else: the
remembered sign-in password, and a mail password if this installation was
given one of its own. The vault (Windows Credential Manager, via
`keyring`) encrypts entries per user account, so a secret saved here is
neither in a file this application writes nor readable by another user of
the same computer.

That covers everything except one thing it structurally cannot: a secret
the build has to arrive with, because no one will ever visit the machine
to type it in. There is exactly one — the vendor's own mail account,
which "Forgot password" sends from — and it travels in the build instead.
`app/config/provisioning.py` is where that lives and where the reasoning
for it is set out in full, including what it does and does not protect.
The vault still comes first wherever it holds an entry, so an
installation set up by hand keeps the account it was given.

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
that is not an address cannot collide with one.

The same name is used inside the provisioning bundle, so the two places a
mail password can come from cannot end up calling it different things."""

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
