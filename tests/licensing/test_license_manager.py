"""The application's view of licensing: one verdict, and feature checks.

Exercised against a fake provider as well as the real one — the manager
must behave the same whichever provider is behind it, since replacing
that provider with the licensing server's is the whole point of the
seam.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import pytest

from app.application.licensing.manager import LicenseManager
from app.domain.licensing.errors import FeatureNotLicensedError, InvalidLicenseError
from app.domain.licensing.ports import LicenseProvider
from app.domain.licensing.state import LicenseState
from app.domain.licensing.status import LicenseStatus

from ._helpers import NOW, Issuer, build_provider


@dataclass(slots=True)
class StubProvider(LicenseProvider):
    """A provider that answers whatever the test needs, and counts reads."""

    state: LicenseState
    reads: int = field(default=0, init=False)

    def current_state(self) -> LicenseState:
        self.reads += 1
        return self.state

    def activate(self, license_key: str) -> LicenseState:
        return self.state

    def deactivate(self) -> None:
        self.state = LicenseState.not_activated()


@pytest.fixture()
def issuer() -> Issuer:
    return Issuer()


# ------------------------------------------------------------ caching


def test_the_licence_is_read_once_however_many_callers_ask() -> None:
    """The gate, the licence screen and every feature check must see one
    verdict — and re-reading a file and a signature for each buys
    nothing."""
    provider = StubProvider(LicenseState(status=LicenseStatus.ACTIVE))
    manager = LicenseManager(provider)

    manager.state()
    manager.state()
    manager.is_usable()

    assert provider.reads == 1


def test_refreshing_asks_the_provider_again() -> None:
    provider = StubProvider(LicenseState(status=LicenseStatus.ACTIVE))
    manager = LicenseManager(provider)
    manager.state()

    provider.state = LicenseState.not_activated()

    assert manager.refresh().status is LicenseStatus.NOT_ACTIVATED
    assert manager.state().status is LicenseStatus.NOT_ACTIVATED


def test_activating_updates_what_every_later_caller_sees(
    tmp_path: Path, issuer: Issuer
) -> None:
    manager = LicenseManager(build_provider(tmp_path, issuer))
    assert not manager.is_usable()

    manager.activate(issuer.issue())

    assert manager.is_usable()
    assert manager.state().status is LicenseStatus.ACTIVE


def test_deactivating_updates_what_every_later_caller_sees(
    tmp_path: Path, issuer: Issuer
) -> None:
    manager = LicenseManager(build_provider(tmp_path, issuer))
    manager.activate(issuer.issue())

    manager.deactivate()

    assert not manager.is_usable()
    assert manager.state().status is LicenseStatus.NOT_ACTIVATED


def test_a_refused_key_reaches_the_caller_with_its_reason(
    tmp_path: Path, issuer: Issuer
) -> None:
    manager = LicenseManager(build_provider(tmp_path, issuer))

    with pytest.raises(InvalidLicenseError, match="different installation"):
        manager.activate(issuer.issue(installation_id="another-machine"))


# ------------------------------------------------------------ usability


@pytest.mark.parametrize(
    ("state", "usable"),
    [
        (LicenseState(status=LicenseStatus.ACTIVE), True),
        (LicenseState(status=LicenseStatus.EXPIRING_SOON, days_remaining=3), True),
        (LicenseState(status=LicenseStatus.EXPIRED, in_grace=True), True),
        (LicenseState(status=LicenseStatus.EXPIRED), False),
        (LicenseState(status=LicenseStatus.SUSPENDED), False),
        (LicenseState(status=LicenseStatus.REVOKED), False),
        (LicenseState.invalid("edited"), False),
        (LicenseState.not_activated(), False),
    ],
    ids=[
        "active",
        "expiring soon",
        "expired in grace",
        "expired past grace",
        "suspended",
        "revoked",
        "invalid",
        "not activated",
    ],
)
def test_which_states_open_the_app(state: LicenseState, usable: bool) -> None:
    assert LicenseManager(StubProvider(state)).is_usable() is usable


# ----------------------------------------------------------- features


def test_a_feature_the_licence_lists_is_available(tmp_path: Path, issuer: Issuer) -> None:
    manager = LicenseManager(build_provider(tmp_path, issuer))
    manager.activate(issuer.issue(features=["reports"]))

    assert manager.has_feature("reports")
    manager.require_feature("reports")


def test_a_feature_the_licence_does_not_list_is_refused(tmp_path: Path, issuer: Issuer) -> None:
    manager = LicenseManager(build_provider(tmp_path, issuer))
    manager.activate(issuer.issue(features=["reports"]))

    assert not manager.has_feature("payroll")
    with pytest.raises(FeatureNotLicensedError, match="payroll"):
        manager.require_feature("payroll")


def test_no_feature_is_available_without_a_licence(tmp_path: Path, issuer: Issuer) -> None:
    manager = LicenseManager(build_provider(tmp_path, issuer))

    assert not manager.has_feature("reports")
    with pytest.raises(FeatureNotLicensedError):
        manager.require_feature("reports")


def test_an_expired_licence_entitles_the_shop_to_nothing_it_lists(
    tmp_path: Path, issuer: Issuer
) -> None:
    """The features are still written in the key. They stop applying the
    moment the licence stops opening the app."""
    expires_at = NOW + timedelta(days=30)
    provider = build_provider(tmp_path, issuer)
    provider.activate(issuer.issue(expires_at=expires_at.isoformat(), grace_days=0))

    later = LicenseManager(build_provider(tmp_path, issuer, now=expires_at + timedelta(days=1)))

    assert not later.has_feature("reports")
