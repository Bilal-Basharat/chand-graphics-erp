"""What the licence view model owes the two screens built on it.

Both the licence page and the activation dialog read this one object, so
it is where two things have to be right: which signal means somebody did
something, and who the shop is told to call.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from app.infrastructure.licensing.file_installation_identity import FileInstallationIdentity
from app.presentation.license_watch import LicenseWatcher
from app.presentation.viewmodels.license_viewmodel import LicenseViewModel

from ._helpers import NOW, FakeClock, Issuer, build_settings, build_watcher

EXPIRES_AT = NOW + timedelta(days=30)
GRACE_DAYS = 7


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture()
def watcher(tmp_path: Path, clock: FakeClock) -> LicenseWatcher:
    issuer = Issuer()
    watcher = build_watcher(tmp_path, issuer, clock)
    watcher.manager.activate(
        issuer.issue(expires_at=EXPIRES_AT.isoformat(), grace_days=GRACE_DAYS)
    )
    watcher.check()
    return watcher


@pytest.fixture()
def view_model(tmp_path: Path, watcher: LicenseWatcher) -> LicenseViewModel:
    return LicenseViewModel(
        watcher,
        FileInstallationIdentity(tmp_path / "installation.json"),
        build_settings(),
    )


# ------------------------------------------------- news is not an action

# The activation dialog closes itself when a key is accepted. It used to
# close on `stateChanged` — which the watcher also emits for the clock,
# for every timer fire and for every window activation. Opening the dialog
# raised a window, Qt reported the application active, the watcher
# re-checked, and the dialog read its own news as an answer and shut. A
# shop inside its grace period, which is precisely when renewing matters,
# could not keep the key box on screen long enough to paste into it.


def test_the_clock_running_out_is_not_an_activation(view_model, watcher, clock):
    """Expiry arrives, the licence goes into grace, everything on screen
    is told — and nothing may take that for a key having been entered."""
    states, activations = [], []
    view_model.stateChanged.connect(states.append)
    view_model.activated.connect(activations.append)

    clock.move_to(EXPIRES_AT + timedelta(days=1))
    watcher.check()

    assert [state.in_grace for state in states] == [True]
    assert activations == []


def test_looking_again_at_an_untouched_licence_is_not_an_activation(view_model, watcher):
    """Coming back to the window re-checks, and a shop alt-tabbing while
    the dialog is open must not have it snatched away."""
    activations = []
    view_model.activated.connect(activations.append)

    watcher.check()
    watcher.check()

    assert activations == []


def test_opening_the_licence_screen_is_not_an_activation(view_model):
    states, activations = [], []
    view_model.stateChanged.connect(states.append)
    view_model.activated.connect(activations.append)

    view_model.load()

    assert len(states) == 1
    assert activations == []


# ----------------------------------------------------- who to call

def test_the_support_details_are_the_build_s_own(view_model):
    assert view_model.support_details == [
        ("Developed by", "Test Devs"),
        ("Email", "dev@example.com"),
        ("Phone", "0300 0000000"),
    ]


def test_a_contact_nobody_filled_in_is_left_out(tmp_path, watcher):
    """Better a shorter card than one offering a blank to ring."""
    view_model = LicenseViewModel(
        watcher,
        FileInstallationIdentity(tmp_path / "installation.json"),
        build_settings(developer_email="", developer_contact=""),
    )

    assert view_model.support_details == [("Developed by", "Test Devs")]
