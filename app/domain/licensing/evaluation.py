"""The licensing rules themselves: entitlement plus clock -> verdict.

Kept as one pure function, deliberately. Everything around it — reading a
file, checking a signature, talking to a server one day — is replaceable
infrastructure, and none of it should be able to change what "expired"
means. This is also the whole of what a test needs to exercise the rules:
no files, no keys, no Qt.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.licensing.entitlement import LicenseEntitlement
from app.domain.licensing.state import LicenseState
from app.domain.licensing.status import LicenseStatus


def evaluate_entitlement(
    entitlement: LicenseEntitlement,
    *,
    now: datetime,
    product_code: str,
    installation_id: str,
    expiring_soon_days: int,
) -> LicenseState:
    """Decide what a verified entitlement allows on this installation.

    The signature is assumed already checked — this answers the questions
    that remain once the licence is known to be genuine: is it ours, is it
    for this machine, is it still in force.

    Args:
        now: The current time, passed in rather than read, so expiry is
            testable and the whole app keeps one clock.
        expiring_soon_days: How long before expiry to start warning.
    """
    if expiring_soon_days < 0:
        raise ValueError("expiring_soon_days cannot be negative")

    if entitlement.product_code != product_code:
        return LicenseState.invalid(
            f"This licence was issued for a different product ({entitlement.product_code})."
        )

    if entitlement.is_bound_to_installation and entitlement.installation_id != installation_id:
        return LicenseState.invalid(
            "This licence was issued for a different installation. "
            "Ask for a licence matching this installation ID."
        )

    if entitlement.issued_status is LicenseStatus.SUSPENDED:
        return LicenseState(
            status=LicenseStatus.SUSPENDED,
            entitlement=entitlement,
            message="This licence is suspended. Please contact your supplier.",
        )

    if entitlement.issued_status is LicenseStatus.REVOKED:
        return LicenseState(
            status=LicenseStatus.REVOKED,
            entitlement=entitlement,
            message="This licence has been revoked. Please contact your supplier.",
        )

    expires_at = entitlement.expires_at
    if expires_at is None:
        return LicenseState(status=LicenseStatus.ACTIVE, entitlement=entitlement)

    if now < expires_at:
        return _live(entitlement, now, expires_at, expiring_soon_days)
    return _expired(entitlement, now, expires_at)


def _live(
    entitlement: LicenseEntitlement,
    now: datetime,
    expires_at: datetime,
    expiring_soon_days: int,
) -> LicenseState:
    # Whole days only: a licence with eleven hours left has "0 days"
    # remaining, which is what the shop should be told.
    days_remaining = (expires_at - now).days

    if days_remaining <= expiring_soon_days:
        return LicenseState(
            status=LicenseStatus.EXPIRING_SOON,
            entitlement=entitlement,
            days_remaining=days_remaining,
            message=_renewal_notice("This licence expires", days_remaining),
        )

    return LicenseState(
        status=LicenseStatus.ACTIVE,
        entitlement=entitlement,
        days_remaining=days_remaining,
    )


def _expired(
    entitlement: LicenseEntitlement,
    now: datetime,
    expires_at: datetime,
) -> LicenseState:
    grace_ends_at = expires_at + timedelta(days=entitlement.grace_days)

    if now < grace_ends_at:
        days_remaining = (grace_ends_at - now).days
        return LicenseState(
            status=LicenseStatus.EXPIRED,
            entitlement=entitlement,
            days_remaining=days_remaining,
            in_grace=True,
            message=_grace_notice(days_remaining),
        )

    return LicenseState(
        status=LicenseStatus.EXPIRED,
        entitlement=entitlement,
        in_grace=False,
        message=(
            f"This licence expired on {expires_at:%d %b %Y}. "
            "Enter a renewed licence key to continue."
        ),
    )


def _grace_notice(days_remaining: int) -> str:
    """Said as how long is left, not as when it ends — "continues in 4
    days" reads as though access were coming back."""
    if days_remaining == 0:
        left = "for the rest of today"
    elif days_remaining == 1:
        left = "for 1 more day"
    else:
        left = f"for {days_remaining} more days"
    return f"This licence has expired. Access continues {left}. Please arrange a renewal."


def _renewal_notice(lead: str, days_remaining: int) -> str:
    if days_remaining == 0:
        when = "today"
    elif days_remaining == 1:
        when = "in 1 day"
    else:
        when = f"in {days_remaining} days"
    return f"{lead} {when}. Please arrange a renewal."
