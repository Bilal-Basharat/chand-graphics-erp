"""What a genuine licence entitles this installation to, and when it stops.

Every case here is one a real shop reaches: the wrong product, the day
before expiry, the week after it, a key issued for the machine at the
other branch, a licence pulled while a dispute is settled.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from app.domain.licensing.activation import LicenseActivation
from app.domain.licensing.errors import InvalidLicenseError
from app.domain.licensing.status import LicenseStatus

from ._helpers import EXPIRING_SOON_DAYS, NOW, Issuer, build_provider


@pytest.fixture()
def issuer() -> Issuer:
    return Issuer()


# ---------------------------------------------------------- no licence


def test_an_installation_with_no_licence_is_not_activated(tmp_path: Path, issuer: Issuer) -> None:
    state = build_provider(tmp_path, issuer).current_state()

    assert state.status is LicenseStatus.NOT_ACTIVATED
    assert not state.is_usable
    assert state.entitlement is None


def test_a_licence_file_full_of_rubbish_reads_as_no_licence(
    tmp_path: Path, issuer: Issuer
) -> None:
    (tmp_path / "license.json").write_text("}{ not json", encoding="utf-8")

    assert build_provider(tmp_path, issuer).current_state().status is LicenseStatus.NOT_ACTIVATED


# ------------------------------------------------------------- product


def test_a_licence_for_another_product_is_refused(tmp_path: Path, issuer: Issuer) -> None:
    provider = build_provider(tmp_path, issuer, product_code="CHAND_GRAPHICS_ERP")

    with pytest.raises(InvalidLicenseError, match="different product"):
        provider.activate(issuer.issue(product_code="SOME_OTHER_ERP"))


# -------------------------------------------------------------- expiry


@pytest.mark.parametrize(
    ("days_until_expiry", "expected"),
    [
        (365, LicenseStatus.ACTIVE),
        (EXPIRING_SOON_DAYS + 1, LicenseStatus.ACTIVE),
        (EXPIRING_SOON_DAYS, LicenseStatus.EXPIRING_SOON),
        (1, LicenseStatus.EXPIRING_SOON),
    ],
)
def test_the_warning_starts_at_the_configured_distance_from_expiry(
    tmp_path: Path, issuer: Issuer, days_until_expiry: int, expected: LicenseStatus
) -> None:
    provider = build_provider(tmp_path, issuer)
    license_key = issuer.issue(expires_at=(NOW + timedelta(days=days_until_expiry)).isoformat())

    state = provider.activate(license_key)

    assert state.status is expected
    assert state.is_usable


def test_a_perpetual_licence_never_counts_down(tmp_path: Path, issuer: Issuer) -> None:
    provider = build_provider(tmp_path, issuer, now=NOW + timedelta(days=36500))

    state = provider.activate(issuer.issue(expires_at=None))

    assert state.status is LicenseStatus.ACTIVE
    assert state.days_remaining is None


def test_an_expired_licence_keeps_working_through_its_grace_period(
    tmp_path: Path, issuer: Issuer
) -> None:
    expires_at = NOW + timedelta(days=30)
    provider = build_provider(tmp_path, issuer, now=expires_at + timedelta(days=3))

    state = provider.activate(issuer.issue(expires_at=expires_at.isoformat(), grace_days=7))

    assert state.status is LicenseStatus.EXPIRED
    assert state.in_grace
    assert state.is_usable
    # Days of grace left, not days of licence: 7 granted, 3 used.
    assert state.days_remaining == 4


def test_an_expired_licence_stops_working_once_grace_runs_out(
    tmp_path: Path, issuer: Issuer
) -> None:
    expires_at = NOW + timedelta(days=30)
    provider = build_provider(tmp_path, issuer, now=expires_at + timedelta(days=8))
    license_key = issuer.issue(expires_at=expires_at.isoformat(), grace_days=7)

    with pytest.raises(InvalidLicenseError, match="expired"):
        provider.activate(license_key)


def test_a_licence_issued_without_grace_stops_the_moment_it_expires(
    tmp_path: Path, issuer: Issuer
) -> None:
    expires_at = NOW + timedelta(days=30)
    provider = build_provider(tmp_path, issuer, now=expires_at + timedelta(minutes=1))
    license_key = issuer.issue(expires_at=expires_at.isoformat(), grace_days=0)

    with pytest.raises(InvalidLicenseError):
        provider.activate(license_key)


def test_a_licence_that_expires_while_the_app_is_installed_stops_at_the_next_start(
    tmp_path: Path, issuer: Issuer
) -> None:
    """Activated inside its term, read back long after it — and after the
    grace window too, so nothing is left to fall back on."""
    expires_at = NOW + timedelta(days=30)
    provider = build_provider(tmp_path, issuer)
    provider.activate(issuer.issue(expires_at=expires_at.isoformat(), grace_days=7))

    later = build_provider(tmp_path, issuer, now=expires_at + timedelta(days=8))
    state = later.current_state()

    assert state.status is LicenseStatus.EXPIRED
    assert not state.in_grace
    assert not state.is_usable


# --------------------------------------------- suspension and revocation


@pytest.mark.parametrize(
    ("issued_status", "expected"),
    [("SUSPENDED", LicenseStatus.SUSPENDED), ("REVOKED", LicenseStatus.REVOKED)],
)
def test_a_licence_the_vendor_has_withdrawn_does_not_open_the_app(
    tmp_path: Path, issuer: Issuer, issued_status: str, expected: LicenseStatus
) -> None:
    provider = build_provider(tmp_path, issuer)
    license_key = issuer.issue(status=issued_status)

    with pytest.raises(InvalidLicenseError):
        provider.activate(license_key)

    # And a licence withdrawn *after* it was activated is refused on the
    # next start, which is how a suspension actually reaches a shop.
    provider.store.save(
        LicenseActivation(
            license_key=license_key,
            installation_id=provider.identity.installation_id(),
            activated_at=NOW,
        )
    )
    state = provider.current_state()

    assert state.status is expected
    assert not state.is_usable


# ------------------------------------------------------------- binding


def test_a_licence_issued_for_another_installation_is_refused(
    tmp_path: Path, issuer: Issuer
) -> None:
    provider = build_provider(tmp_path, issuer)

    with pytest.raises(InvalidLicenseError, match="different installation"):
        provider.activate(issuer.issue(installation_id="somebody-elses-machine"))


def test_a_licence_issued_for_this_installation_is_accepted(
    tmp_path: Path, issuer: Issuer
) -> None:
    provider = build_provider(tmp_path, issuer)
    installation_id = provider.identity.installation_id()

    state = provider.activate(issuer.issue(installation_id=installation_id))

    assert state.status is LicenseStatus.ACTIVE


def test_a_bound_licence_copied_to_another_installation_stops_there(
    tmp_path: Path, issuer: Issuer
) -> None:
    """The key file travels; the installation id it was signed against
    does not."""
    first = build_provider(tmp_path / "shop", issuer)
    license_key = issuer.issue(installation_id=first.identity.installation_id())
    first.activate(license_key)

    second = build_provider(tmp_path / "branch", issuer)

    with pytest.raises(InvalidLicenseError, match="different installation"):
        second.activate(license_key)


def test_a_site_licence_is_not_tied_to_any_installation(tmp_path: Path, issuer: Issuer) -> None:
    """`installation_id: null` is a deliberate choice by the issuer, and
    offline it means what it says — which is why the issuing tool warns
    when one is signed."""
    provider = build_provider(tmp_path, issuer)

    assert provider.activate(issuer.issue(installation_id=None)).is_usable


# ------------------------------------------------ activation lifecycle


def test_activating_stores_the_licence_for_the_next_start(
    tmp_path: Path, issuer: Issuer
) -> None:
    provider = build_provider(tmp_path, issuer)
    provider.activate(issuer.issue())

    restarted = build_provider(tmp_path, issuer)

    assert restarted.current_state().status is LicenseStatus.ACTIVE


def test_entering_the_same_key_twice_is_harmless(tmp_path: Path, issuer: Issuer) -> None:
    """Re-activating an installation it is already on consumes nothing —
    a shop that pastes the key again after a support call is not out a
    device."""
    provider = build_provider(tmp_path, issuer)
    license_key = issuer.issue(installation_id=None, max_devices=1)

    provider.activate(license_key)
    provider.activate(license_key)

    assert provider.current_state().status is LicenseStatus.ACTIVE
    assert provider.store.load().installation_id == provider.identity.installation_id()  # type: ignore[union-attr]


def test_a_renewal_replaces_the_licence_in_place(tmp_path: Path, issuer: Issuer) -> None:
    provider = build_provider(tmp_path, issuer, now=NOW + timedelta(days=364))
    provider.activate(issuer.issue())
    assert provider.current_state().status is LicenseStatus.EXPIRING_SOON

    renewed = issuer.issue(expires_at=(NOW + timedelta(days=730)).isoformat())

    assert provider.activate(renewed).status is LicenseStatus.ACTIVE
    assert provider.current_state().status is LicenseStatus.ACTIVE


def test_deactivating_returns_the_installation_to_unlicensed(
    tmp_path: Path, issuer: Issuer
) -> None:
    provider = build_provider(tmp_path, issuer)
    provider.activate(issuer.issue())

    provider.deactivate()

    assert provider.current_state().status is LicenseStatus.NOT_ACTIVATED
    assert not (tmp_path / "license.json").exists()


def test_deactivating_an_installation_that_has_no_licence_is_not_an_error(
    tmp_path: Path, issuer: Issuer
) -> None:
    build_provider(tmp_path, issuer).deactivate()


def test_a_licence_activated_against_a_lost_identity_asks_to_be_activated_again(
    tmp_path: Path, issuer: Issuer
) -> None:
    """One activation record per installation is the only device count
    this side can keep honestly, so a record naming another installation
    is not trusted."""
    provider = build_provider(tmp_path, issuer)
    provider.activate(issuer.issue(installation_id=None))
    (tmp_path / "installation.json").unlink()

    state = build_provider(tmp_path, issuer).current_state()

    assert state.status is LicenseStatus.INVALID
    assert "activate it again" in (state.message or "")


# -------------------------------------------------------- device limit


@pytest.mark.parametrize("max_devices", [1, 3, 25])
def test_the_device_limit_is_whatever_the_licence_says(
    tmp_path: Path, issuer: Issuer, max_devices: int
) -> None:
    """Read from the licence and reported, never decided here. Enforcing
    a count above one needs a view of every installation, which is the
    licensing server's job — this side must not invent a limit of its
    own in the meantime."""
    provider = build_provider(tmp_path, issuer)

    state = provider.activate(issuer.issue(max_devices=max_devices))

    assert state.entitlement is not None
    assert state.entitlement.max_devices == max_devices


# ---------------------------------------------------------- entitlements


def test_the_features_a_licence_lists_are_the_features_it_carries(
    tmp_path: Path, issuer: Issuer
) -> None:
    provider = build_provider(tmp_path, issuer)

    state = provider.activate(issuer.issue(features=["reports", "multi_user"]))

    assert state.entitlement is not None
    assert state.entitlement.has_feature("reports")
    assert state.entitlement.has_feature("multi_user")
    assert not state.entitlement.has_feature("payroll")
