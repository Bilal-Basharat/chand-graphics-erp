"""
Remembered sign-in credentials, for autofilling the login form.

Split deliberately across two stores, because the two halves carry very
different risk:

- **Email** is not a secret. It goes in a small JSON file beside the
  session file, same as any other UI preference.
- **Password** is a secret and never touches a file this app writes. It
  goes to the operating system's credential vault (Windows Credential
  Manager via `keyring`), which encrypts it per user account. Writing a
  password into our own JSON — or "encrypting" it with a key shipped in
  the same repo — would be security theatre.

If no vault backend is available, password storage degrades to "off"
rather than falling back to plaintext: `passwords_supported` reports that
so the UI can say so plainly instead of silently dropping the password.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# The service name the vault entries are filed under. Visible to the user
# in Windows Credential Manager, so it should read as this application.
_KEYRING_SERVICE = "Chand Graphics ERP"

try:  # pragma: no cover - depends on the machine's available backends
    import keyring
    from keyring.errors import KeyringError

    _keyring_available = True
except ImportError:  # pragma: no cover
    keyring = None  # type: ignore[assignment]
    KeyringError = Exception  # type: ignore[assignment, misc]
    _keyring_available = False


def _vault_usable() -> bool:
    """True when a real, non-failing backend is present.

    `keyring` always imports; whether it has a usable backend depends on
    the machine, and the "fail" backend raises on every call.
    """
    if not _keyring_available:
        return False
    try:
        backend = keyring.get_keyring()
    except Exception:  # pragma: no cover - defensive
        return False
    return "fail" not in type(backend).__module__.lower()


@dataclass(slots=True)
class RememberedCredentials:
    email: str | None = None
    password: str | None = None

    @property
    def has_email(self) -> bool:
        return bool(self.email)


class CredentialStore:
    def __init__(self, preferences_path: Path) -> None:
        self._path = preferences_path
        self._passwords_supported = _vault_usable()

    @property
    def passwords_supported(self) -> bool:
        """False when the OS has no credential vault we can use."""
        return self._passwords_supported

    # ---------------- read ----------------

    def load(self) -> RememberedCredentials:
        email = self._read_preferences().get("email")
        if not isinstance(email, str) or not email:
            return RememberedCredentials()

        return RememberedCredentials(email=email, password=self._read_password(email))

    # ---------------- write ----------------

    def remember(self, email: str, password: str) -> None:
        """Store the email, and the password too when a vault is available."""
        email = email.strip()
        if not email:
            return

        previous = self._read_preferences().get("email")
        if isinstance(previous, str) and previous and previous != email:
            # Switching accounts: don't leave the old one's secret behind.
            self._delete_password(previous)

        self._write_preferences({"email": email})
        if self._passwords_supported:
            self._write_password(email, password)

    def forget(self) -> None:
        email = self._read_preferences().get("email")
        if isinstance(email, str) and email:
            self._delete_password(email)
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove saved sign-in preferences")

    # ---------------- preferences file ----------------

    def _read_preferences(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Saved sign-in preferences unreadable; ignoring them")
            return {}

    def _write_preferences(self, payload: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
            temp_path.write_text(json.dumps(payload), encoding="utf-8")
            temp_path.replace(self._path)
        except OSError:
            logger.exception("Could not save sign-in preferences")

    # ---------------- OS credential vault ----------------

    def _read_password(self, email: str) -> str | None:
        if not self._passwords_supported:
            return None
        try:
            return keyring.get_password(_KEYRING_SERVICE, email)
        except KeyringError:
            logger.exception("Could not read the saved password from the credential vault")
            return None

    def _write_password(self, email: str, password: str) -> None:
        try:
            keyring.set_password(_KEYRING_SERVICE, email, password)
        except KeyringError:
            logger.exception("Could not save the password to the credential vault")

    def _delete_password(self, email: str) -> None:
        if not self._passwords_supported:
            return
        try:
            keyring.delete_password(_KEYRING_SERVICE, email)
        except KeyringError:
            # Nothing stored for that address — nothing to undo.
            logger.debug("No saved password to remove for %s", email)
