"""
Remembered sign-in credentials, for autofilling the login form.

Split deliberately across two stores, because the two halves carry very
different risk:

- **Email** is not a secret. It goes in a small JSON file beside the
  session file, same as any other UI preference.
- **Password** is a secret and never touches a file this app writes. It
  goes to the operating system's credential vault, which encrypts it per
  user account — see `infrastructure/security/secret_vault.py`, which
  every secret in this application goes through.

If no vault backend is available, password storage degrades to "off"
rather than falling back to plaintext: `passwords_supported` reports that
so the UI can say so plainly instead of silently dropping the password.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.security.secret_vault import SecretVault

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RememberedCredentials:
    email: str | None = None
    password: str | None = None

    @property
    def has_email(self) -> bool:
        return bool(self.email)


class CredentialStore:
    def __init__(self, preferences_path: Path, vault: SecretVault | None = None) -> None:
        self._path = preferences_path
        # Filed under the email address, which is what the vault entry is
        # keyed by — one saved password per account, as the sign-in screen
        # offers.
        self._vault = vault or SecretVault()

    @property
    def passwords_supported(self) -> bool:
        """False when the OS has no credential vault we can use."""
        return self._vault.is_available

    # ---------------- read ----------------

    def load(self) -> RememberedCredentials:
        email = self._read_preferences().get("email")
        if not isinstance(email, str) or not email:
            return RememberedCredentials()

        return RememberedCredentials(email=email, password=self._vault.get(email))

    # ---------------- write ----------------

    def remember(self, email: str, password: str) -> None:
        """Store the email, and the password too when a vault is available."""
        email = email.strip()
        if not email:
            return

        previous = self._read_preferences().get("email")
        if isinstance(previous, str) and previous and previous != email:
            # Switching accounts: don't leave the old one's secret behind.
            self._vault.delete(previous)

        self._write_preferences({"email": email})
        self._vault.set(email, password)

    def forget(self) -> None:
        email = self._read_preferences().get("email")
        if isinstance(email, str) and email:
            self._vault.delete(email)
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
