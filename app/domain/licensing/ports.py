from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.licensing.activation import LicenseActivation
from app.domain.licensing.state import LicenseState


class LicenseProvider(ABC):
    """Where a licence comes from, and what it currently says.

    The one seam this whole feature is built around. Today the only
    implementation reads a key the shop typed in and verifies it offline.
    When the licensing server exists, a second implementation fetches and
    renews the same signed entitlement over HTTP and caches it through
    the same store — and nothing above this line changes.
    """

    @abstractmethod
    def current_state(self) -> LicenseState:
        """Evaluate the stored licence. Never raises; refusals come back
        as a `LicenseState` carrying the reason."""
        raise NotImplementedError

    @abstractmethod
    def activate(self, license_key: str) -> LicenseState:
        """Accept a licence key for this installation.

        Raises:
            InvalidLicenseError: If the key cannot be used here, with a
                reason the shop can act on.
        """
        raise NotImplementedError

    @abstractmethod
    def deactivate(self) -> None:
        """Release this installation. Idempotent."""
        raise NotImplementedError


class LicenseStore(ABC):
    """Where the activation record is kept — never inside erp.db.

    The business database is backed up, restored, copied between machines
    and rebuilt by migrations; a licence riding along with it would be
    every one of those a licence must not be.
    """

    @abstractmethod
    def load(self) -> LicenseActivation | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, activation: LicenseActivation) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError


class InstallationIdentity(ABC):
    """This installation's stable identifier.

    Generated once, kept for the life of the installation, and quoted by
    the shop when asking for a licence — the vendor signs it into the
    key, which is what stops that key working anywhere else.
    """

    @abstractmethod
    def installation_id(self) -> str:
        raise NotImplementedError


class LicenseSignatureVerifier(ABC):
    """Verifies a licence signature against a trusted public key.

    Abstract so the domain, and the tests that exercise it, never depend
    on a particular cryptography library — and so that rotating to a new
    signing key is a matter of `key_id`, not of new code.
    """

    @abstractmethod
    def verify(self, message: bytes, signature: bytes, key_id: str) -> bool:
        """True only if `signature` is this `key_id`'s signature over
        `message`. An unknown `key_id` is a `False`, not an error."""
        raise NotImplementedError
