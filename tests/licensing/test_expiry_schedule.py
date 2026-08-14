"""A licence that runs out while the app is open, to the second.

The case this file exists for: the ERP is opened on Monday morning and
left open all week. Every assertion here is made against a clock the test
moves, on one watcher that is never rebuilt — because "it is correct at
the next start" was exactly the old behaviour, and a test that restarts
anything would pass against it.

No QApplication and no event loop. The watcher's timer is connected to
`check()` and nothing else, so calling `check()` is precisely what a
firing timer does; what the timer was *set for* is asserted separately
through `next_transition_at()`.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.domain.licensing.status import LicenseStatus
from app.presentation.license_display import status_notice
from app.presentation.license_watch import LicenseWatcher

from ._helpers import EXPIRING_SOON_DAYS, NOW, FakeClock, Issuer, build_watcher

# An expiry with hours, minutes and seconds in it, because that is what a
# licence carries and what the app must enforce.
EXPIRES_AT = datetime(2026, 9, 12, 17, 30, 45)
GRACE_DAYS = 7
GRACE_ENDS_AT = EXPIRES_AT + timedelta(days=GRACE_DAYS)
WARNING_STARTS_AT = EXPIRES_AT - timedelta(days=EXPIRING_SOON_DAYS + 1)


@pytest.fixture()
def issuer() -> Issuer:
    return Issuer()


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture()
def watcher(tmp_path: Path, issuer: Issuer, clock: FakeClock) -> LicenseWatcher:
    """An installation licensed until `EXPIRES_AT`, activated well inside
    its term — the ordinary shop, on the ordinary day."""
    watcher = build_watcher(tmp_path, issuer, clock)
    watcher.manager.activate(
        issuer.issue(expires_at=EXPIRES_AT.isoformat(), grace_days=GRACE_DAYS)
    )
    watcher.check()
    return watcher


# ------------------------------------------------------- what is scheduled


def test_the_first_thing_scheduled_is_the_start_of_the_warning_window(watcher):
    """Nothing else would ever put the warning on screen: an app already
    open when the fortnight begins has no restart to notice it at."""
    assert watcher.state().status is LicenseStatus.ACTIVE
    assert watcher.next_transition_at() == WARNING_STARTS_AT


def test_a_perpetual_licence_schedules_nothing(tmp_path, issuer, clock):
    watcher = build_watcher(tmp_path, issuer, clock)
    watcher.manager.activate(issuer.issue(expires_at=None))

    watcher.check()

    assert watcher.next_transition_at() is None


def test_an_installation_with_no_licence_schedules_nothing(tmp_path, issuer, clock):
    """There is no verdict here that time will change, and the startup
    gate is already standing in front of it."""
    watcher = build_watcher(tmp_path, issuer, clock)

    watcher.check()

    assert watcher.state().status is LicenseStatus.NOT_ACTIVATED
    assert watcher.next_transition_at() is None


def test_a_wait_longer_than_qt_can_hold_is_still_armed(tmp_path, issuer, clock):
    """Qt takes a 32-bit millisecond interval and raises OverflowError
    above it — roughly 24 days. A three-year licence must not bring the
    app down the moment it is activated."""
    distant = NOW + timedelta(days=3 * 365)
    watcher = build_watcher(tmp_path, issuer, clock)
    watcher.manager.activate(issuer.issue(expires_at=distant.isoformat()))

    watcher.check()

    assert watcher.next_transition_at() == distant - timedelta(days=EXPIRING_SOON_DAYS + 1)


# ------------------------------------------------------------ the crossings


def test_just_before_expiry_the_licence_is_still_in_force(watcher, clock):
    clock.move_to(EXPIRES_AT - timedelta(seconds=1))

    state = watcher.check()

    assert state.status is LicenseStatus.EXPIRING_SOON
    assert state.is_usable
    # To the second: this is the instant the app is scheduled to change at.
    assert watcher.next_transition_at() == EXPIRES_AT


def test_at_the_exact_moment_of_expiry_access_continues_on_grace(watcher, clock):
    clock.move_to(EXPIRES_AT)

    state = watcher.check()

    assert state.status is LicenseStatus.EXPIRED
    assert state.in_grace
    assert state.is_usable
    assert watcher.next_transition_at() == GRACE_ENDS_AT


def test_during_grace_the_shop_is_still_trading(watcher, clock):
    clock.move_to(EXPIRES_AT + timedelta(days=3))

    state = watcher.check()

    assert state.in_grace
    assert state.is_usable
    # Days of grace left, not days of licence: 7 granted, 3 used.
    assert state.days_remaining == 4
    assert watcher.next_transition_at() == GRACE_ENDS_AT


def test_at_the_exact_end_of_grace_the_app_is_blocked(watcher, clock):
    clock.move_to(GRACE_ENDS_AT)

    state = watcher.check()

    assert state.status is LicenseStatus.EXPIRED
    assert not state.in_grace
    assert not state.is_usable
    # Nothing further to wait for: no verdict this side of a new key.
    assert watcher.next_transition_at() is None


def test_after_grace_it_stays_blocked(watcher, clock):
    clock.move_to(GRACE_ENDS_AT + timedelta(days=5))

    state = watcher.check()

    assert not state.is_usable
    assert watcher.next_transition_at() is None


# --------------------------------------------------- while the app is open


def test_an_app_left_open_across_expiry_stops_by_itself(watcher, clock):
    """The whole point. One watcher, never rebuilt, no restart anywhere:
    the verdict must change under an app that is already running."""
    assert watcher.state().is_usable

    clock.move_to(EXPIRES_AT)
    assert watcher.check().in_grace, "grace should carry the shop past expiry"

    clock.move_to(GRACE_ENDS_AT)

    assert not watcher.check().is_usable


def test_a_renewal_while_the_app_is_open_puts_it_back_to_work(watcher, clock, issuer):
    """And without a restart either — the shop pastes the key it was sent
    into the licence screen and carries on."""
    clock.move_to(GRACE_ENDS_AT)
    watcher.check()
    assert not watcher.state().is_usable

    renewed = EXPIRES_AT + timedelta(days=365)
    watcher.manager.activate(issuer.issue(expires_at=renewed.isoformat()))
    state = watcher.check()

    assert state.status is LicenseStatus.ACTIVE
    assert state.is_usable
    # And the app is now waiting on the new term, not the old one.
    assert watcher.next_transition_at() == renewed - timedelta(days=EXPIRING_SOON_DAYS + 1)


# ------------------------------------------------------------ what is said


def test_a_warning_is_given_once_per_run(watcher, clock):
    """Re-checked on every window activation and every timer fire — a
    shop that alt-tabs twice must not be told twice."""
    clock.move_to(EXPIRES_AT - timedelta(days=1))
    watcher.check()

    first = watcher.take_notice()

    assert first is not None
    assert first.status is LicenseStatus.EXPIRING_SOON
    assert watcher.take_notice() is None

    watcher.check()
    assert watcher.take_notice() is None


def test_each_situation_is_announced_in_its_own_turn(watcher, clock):
    """Expiring, expired-but-trading and locked out are three different
    things to tell a shop, so each gets said once."""
    said = []
    for when in (EXPIRES_AT - timedelta(days=1), EXPIRES_AT, GRACE_ENDS_AT):
        clock.move_to(when)
        watcher.check()
        notice = watcher.take_notice()
        said.append(None if notice is None else (notice.status, notice.in_grace))

    assert said == [
        (LicenseStatus.EXPIRING_SOON, False),
        (LicenseStatus.EXPIRED, True),
        (LicenseStatus.EXPIRED, False),
    ]


def test_a_licence_in_order_is_not_announced_at_all(watcher):
    assert watcher.state().status is LicenseStatus.ACTIVE
    assert watcher.take_notice() is None


def test_the_status_chip_is_empty_until_there_is_something_to_say(watcher, clock):
    assert status_notice(watcher.state()) == ""

    clock.move_to(EXPIRES_AT - timedelta(days=6))

    assert status_notice(watcher.check()) == "Licence expires in 6 days"
