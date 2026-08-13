"""How a licence verdict reads on screen.

Both places that show one — the activation dialog and the licence screen
— name and colour it from here, so a licence in grace cannot look urgent
on one and routine on the other.
"""
from __future__ import annotations

from app.domain.licensing.state import LicenseState
from app.domain.licensing.status import LicenseStatus

# Chip tones the stylesheet already defines for role="tag".
_SUCCESS = "success"
_WARNING = "warning"
_DANGER = "danger"
_MUTED = "muted"

_LABELS: dict[LicenseStatus, str] = {
    LicenseStatus.NOT_ACTIVATED: "Not activated",
    LicenseStatus.ACTIVE: "Active",
    LicenseStatus.EXPIRING_SOON: "Expiring soon",
    LicenseStatus.EXPIRED: "Expired",
    LicenseStatus.SUSPENDED: "Suspended",
    LicenseStatus.REVOKED: "Revoked",
    LicenseStatus.INVALID: "Not valid",
}

_TONES: dict[LicenseStatus, str] = {
    LicenseStatus.NOT_ACTIVATED: _MUTED,
    LicenseStatus.ACTIVE: _SUCCESS,
    LicenseStatus.EXPIRING_SOON: _WARNING,
    LicenseStatus.EXPIRED: _DANGER,
    LicenseStatus.SUSPENDED: _DANGER,
    LicenseStatus.REVOKED: _DANGER,
    LicenseStatus.INVALID: _DANGER,
}


def status_label(state: LicenseState) -> str:
    if state.status is LicenseStatus.EXPIRED and state.in_grace:
        return "Expired — grace period"
    return _LABELS[state.status]


def status_tone(state: LicenseState) -> str:
    """An expired licence that still opens the app is a warning, not a
    failure: the shop can keep trading while the renewal arrives."""
    if state.status is LicenseStatus.EXPIRED and state.in_grace:
        return _WARNING
    return _TONES[state.status]
