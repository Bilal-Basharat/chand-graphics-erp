from enum import StrEnum


class LicenseStatus(StrEnum):
    """What this installation's licence currently allows.

    Three of these members also travel *inside* a signed licence, as the
    state the issuer put it in — `ACTIVE`, `SUSPENDED`, `REVOKED`. The
    rest are conclusions this installation reaches on its own by reading
    the clock (`EXPIRING_SOON`, `EXPIRED`), by finding nothing stored
    (`NOT_ACTIVATED`), or by failing to trust what it found (`INVALID`).

    Deliberately not a member: "in grace". A licence past its expiry that
    is still inside its grace window is `EXPIRED` — the shop must renew —
    and `LicenseState.in_grace` says whether the door is still open
    meanwhile. Folding that into a status would leave every caller unable
    to tell "expired, still working" from "expired, locked out".
    """

    NOT_ACTIVATED = "NOT_ACTIVATED"
    ACTIVE = "ACTIVE"
    EXPIRING_SOON = "EXPIRING_SOON"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"
