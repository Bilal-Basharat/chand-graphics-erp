from __future__ import annotations

from dataclasses import dataclass

from app.domain.licensing.entitlement import LicenseEntitlement
from app.domain.licensing.status import LicenseStatus

_USABLE_STATUSES = frozenset({LicenseStatus.ACTIVE, LicenseStatus.EXPIRING_SOON})


@dataclass(frozen=True, slots=True)
class LicenseState:
    """The verdict on this installation's licence, right now.

    Everything the app needs to decide whether to open, what to warn
    about, and what to tell the shop — in one immutable value. Produced
    by `evaluate_entitlement`, or by the two factories below when there
    is no entitlement to evaluate at all.
    """

    status: LicenseStatus
    entitlement: LicenseEntitlement | None = None
    # Whole days until access stops: until expiry while the licence is
    # live, until the grace window closes once it has expired. `None`
    # when nothing is counting down — a perpetual licence, or a licence
    # that is already refused.
    days_remaining: int | None = None
    in_grace: bool = False
    # Why, in words the shop can act on. Always set when the licence is
    # refused; `None` when it is simply in order.
    message: str | None = None

    @property
    def is_usable(self) -> bool:
        """Whether the ERP may be opened on this installation.

        An expired licence still inside its grace window counts: the shop
        that paid on Friday should not be locked out while the new key
        travels.
        """
        if self.status in _USABLE_STATUSES:
            return True
        return self.status is LicenseStatus.EXPIRED and self.in_grace

    @classmethod
    def not_activated(cls) -> "LicenseState":
        return cls(
            status=LicenseStatus.NOT_ACTIVATED,
            message="This installation has not been activated yet.",
        )

    @classmethod
    def invalid(cls, reason: str) -> "LicenseState":
        return cls(status=LicenseStatus.INVALID, message=reason)
