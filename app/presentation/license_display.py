"""How a licence verdict reads on screen.

Every place that shows one — the activation dialog, the licence screen and
the shell's status chip — names and colours it from here, so a licence in
grace cannot look urgent on one and routine on the other.
"""
from __future__ import annotations

from app.domain.licensing.state import LicenseState
from app.domain.licensing.status import LicenseStatus
from app.presentation.formatting import counted

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


# What the shell's status chip says. Short enough for a strip at the
# bottom of the window, and each one names the thing to do about it — a
# warning with no action in it is a warning people learn to ignore.
_BLOCKED_NOTICES: dict[LicenseStatus, str] = {
    LicenseStatus.NOT_ACTIVATED: "Not activated — enter a licence key",
    LicenseStatus.EXPIRED: "Licence expired — renew to continue",
    LicenseStatus.SUSPENDED: "Licence suspended — contact your supplier",
    LicenseStatus.REVOKED: "Licence revoked — contact your supplier",
    LicenseStatus.INVALID: "Licence not valid — enter a licence key",
}


def status_notice(state: LicenseState) -> str:
    """The one line the status chip carries, or "" when there is none.

    A licence in order says nothing. An indicator that is on screen every
    day is one nobody notices on the day it changes.
    """
    days = state.days_remaining or 0

    if state.status is LicenseStatus.EXPIRING_SOON:
        if days == 0:
            return "Licence expires today"
        return f"Licence expires in {counted(days, 'day')}"

    if state.status is LicenseStatus.EXPIRED and state.in_grace:
        if days == 0:
            return "Licence expired — last day of access"
        return f"Licence expired — {counted(days, 'day')} of access left"

    if state.is_usable:
        return ""
    return _BLOCKED_NOTICES[state.status]
