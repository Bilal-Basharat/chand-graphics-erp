from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.licensing.status import LicenseStatus

# The three states an issuer can put a licence in. The others
# (`EXPIRING_SOON`, `EXPIRED`, `NOT_ACTIVATED`, `INVALID`) are conclusions
# reached here, never claims made by the key itself.
ISSUABLE_STATUSES = frozenset(
    {LicenseStatus.ACTIVE, LicenseStatus.SUSPENDED, LicenseStatus.REVOKED}
)


@dataclass(frozen=True, slots=True)
class LicenseEntitlement:
    """What the vendor signed: who may run which product, until when.

    This is the whole of the licensing model the desktop keeps. It
    carries no subscription history, no payments and no device register —
    those belong to the licensing server, which is authoritative and
    issues this as its verifiable summary.

    Every field here is covered by the signature, so none of it can be
    edited on the customer's machine without the key ceasing to verify.
    """

    license_id: str
    product_code: str
    customer_name: str
    plan_code: str
    # The payload's `status` field: the state the *issuer* put this
    # licence in. Named apart from `LicenseState.status` because that one
    # is the conclusion, and reading them as the same thing is how a
    # revoked licence ends up looking merely expired.
    issued_status: LicenseStatus
    # The installation this key was issued for, which is how one licence
    # is told from another: every installation has its own id and gets its
    # own key. `None` is a site licence — it runs anywhere, and only the
    # server can see where "anywhere" turned out to be.
    installation_id: str | None
    features: frozenset[str]
    issued_at: datetime
    # `None` is perpetual — bought outright, never expires.
    expires_at: datetime | None
    grace_days: int

    def __post_init__(self) -> None:
        if not self.license_id.strip():
            raise ValueError("license_id cannot be empty")
        if not self.product_code.strip():
            raise ValueError("product_code cannot be empty")
        if self.issued_status not in ISSUABLE_STATUSES:
            raise ValueError(f"'{self.issued_status}' is not a licence status an issuer can set")
        if self.grace_days < 0:
            raise ValueError("grace_days cannot be negative")
        if self.expires_at is not None and self.expires_at < self.issued_at:
            raise ValueError("expires_at cannot precede issued_at")

    @property
    def is_perpetual(self) -> bool:
        return self.expires_at is None

    @property
    def is_bound_to_installation(self) -> bool:
        return self.installation_id is not None

    def has_feature(self, feature: str) -> bool:
        return feature in self.features
