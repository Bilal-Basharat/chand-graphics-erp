"""The application's one way in to licensing.

Everything else — startup gate, licence screen, any future feature check
— goes through here and never touches a provider, a store or a key. That
is what keeps the choice between "a key the shop typed in" and "an
entitlement fetched from the licensing server" a one-line change in the
container.

Note what this is *not*: a use case. Licensing is not a business
transaction, has no unit of work, and touches no repository — putting it
through `AuthorizedUseCase` would give it a database session it must
never have and a permission check that has no meaning before anyone has
signed in.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.licensing.errors import FeatureNotLicensedError
from app.domain.licensing.ports import LicenseProvider
from app.domain.licensing.state import LicenseState


@dataclass(slots=True)
class LicenseManager:
    """Reads, caches and changes this installation's licence."""

    provider: LicenseProvider
    _state: LicenseState | None = field(default=None, init=False)

    def state(self) -> LicenseState:
        """The current verdict, evaluated once per run.

        Cached because the licence screen, the startup gate and any
        feature check all ask the same question, and re-reading the file
        and re-checking a signature for each of them buys nothing. A
        licence that expires while the app is open keeps working until
        the next start — the alternative is throwing a shop out of a
        half-finished invoice at midnight.
        """
        if self._state is None:
            self._state = self.provider.current_state()
        return self._state

    def refresh(self) -> LicenseState:
        """Re-read the licence, discarding what was cached."""
        self._state = self.provider.current_state()
        return self._state

    def activate(self, license_key: str) -> LicenseState:
        """Accept a licence key for this installation.

        Raises:
            InvalidLicenseError: If the key cannot be used here.
        """
        self._state = self.provider.activate(license_key)
        return self._state

    def deactivate(self) -> None:
        self.provider.deactivate()
        self._state = self.provider.current_state()

    def is_usable(self) -> bool:
        return self.state().is_usable

    def has_feature(self, feature: str) -> bool:
        """Whether the licence in force includes `feature`.

        False whenever the licence is not usable at all: an expired
        licence entitles the shop to nothing, whatever it lists.
        """
        state = self.state()
        if not state.is_usable or state.entitlement is None:
            return False
        return state.entitlement.has_feature(feature)

    def require_feature(self, feature: str) -> None:
        """
        Raises:
            FeatureNotLicensedError: If the licence does not include it.
        """
        if not self.has_feature(feature):
            raise FeatureNotLicensedError(
                f"Your licence does not include this feature ({feature})."
            )
