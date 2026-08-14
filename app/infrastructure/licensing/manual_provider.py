"""Licensing from a key the shop was given and typed in.

The whole of the current phase: no server, no network, no polling. The
vendor signs an entitlement for one installation, the shop pastes it in
once, and every start after that is a file read and a signature check —
which is why it keeps working on a day the Internet does not.

What this enforces, stated plainly: signature, product, expiry, grace,
suspension, revocation, and the binding to this installation — all of it
offline, and none of it editable on the customer's machine without the
key ceasing to verify. One installation, one id, one key issued against
it, so there is nothing further for this side to count.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from app.domain.licensing.activation import LicenseActivation
from app.domain.licensing.errors import InvalidLicenseError
from app.domain.licensing.evaluation import evaluate_entitlement
from app.domain.licensing.ports import (
    InstallationIdentity,
    LicenseProvider,
    LicenseSignatureVerifier,
    LicenseStore,
)
from app.domain.licensing.state import LicenseState
from app.infrastructure.licensing.license_key import (
    decode_license_key,
    entitlement_from_payload,
)
from app.shared.datetimes import now_pkt

_UNSIGNED = (
    "This licence key was not issued by Chand Graphics. "
    "Please check it was copied in full, or ask for a new one."
)
_REACTIVATE = (
    "This licence was activated on a different installation of this app. "
    "Please activate it again."
)


@dataclass(slots=True)
class ManualLicenseProvider(LicenseProvider):
    store: LicenseStore
    identity: InstallationIdentity
    verifier: LicenseSignatureVerifier
    product_code: str
    expiring_soon_days: int
    # Injected so expiry is a testable rule rather than a wait, and so the
    # whole app reads one clock.
    clock: Callable[[], datetime] = now_pkt

    def current_state(self) -> LicenseState:
        activation = self.store.load()
        if activation is None:
            return LicenseState.not_activated()

        # A key is issued against one installation id, so a record naming
        # another means the identity file was lost or the folder was
        # copied elsewhere. The shop should activate rather than be
        # trusted.
        if activation.installation_id != self.identity.installation_id():
            return LicenseState.invalid(_REACTIVATE)

        try:
            return self._evaluate(activation.license_key)
        except InvalidLicenseError as exc:
            # Reading a licence never raises: a screen that explains why
            # the shop is locked out is worth more than a stack trace.
            return LicenseState.invalid(str(exc))

    def activate(self, license_key: str) -> LicenseState:
        state = self._evaluate(license_key)
        if not state.is_usable:
            raise InvalidLicenseError(state.message or "This licence key cannot be used here.")

        # Overwrites any previous record, which is what makes re-entering
        # the same key harmless and a renewal a one-step job.
        self.store.save(
            LicenseActivation(
                license_key="".join(license_key.split()),
                installation_id=self.identity.installation_id(),
                activated_at=self.clock(),
            )
        )
        return state

    def deactivate(self) -> None:
        self.store.clear()

    def _evaluate(self, license_key: str) -> LicenseState:
        """Decode, verify, then judge.

        Raises:
            InvalidLicenseError: If the key is unreadable or unsigned —
                the two failures that are about the key itself rather
                than about what it entitles this installation to.
        """
        decoded = decode_license_key(license_key)

        # Before anything in the payload is read as fact.
        if not self.verifier.verify(decoded.signed_bytes, decoded.signature, decoded.key_id):
            raise InvalidLicenseError(_UNSIGNED)

        entitlement = entitlement_from_payload(decoded.payload)

        return evaluate_entitlement(
            entitlement,
            now=self.clock(),
            product_code=self.product_code,
            installation_id=self.identity.installation_id(),
            expiring_soon_days=self.expiring_soon_days,
        )
