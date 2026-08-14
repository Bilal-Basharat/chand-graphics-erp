"""The app's one live licence verdict, and the timer that keeps it true.

Licensing used to be settled once at startup and never looked at again: a
shop that opens the ERP on Monday and leaves it open all week ran a week
past its expiry, with the Licence screen still reporting it active. This
is what fixes that, and it does it without polling anything.

The rule is one wake-up, not a loop. When the licence is read, the domain
says exactly when its verdict changes next — the moment the warning
window opens, the moment it expires, the moment grace ends — and a single
single-shot timer is armed for that instant. Nothing runs in between.

What fires is a re-evaluation, never the state that was expected: the
machine may have slept through the transition, the clock may have been
put back, the licence may have been renewed in the meantime. `check()` is
the only way this object ever changes, and it always asks the clock.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication

from app.application.licensing.manager import LicenseManager
from app.domain.licensing.evaluation import next_transition_at
from app.domain.licensing.state import LicenseState
from app.domain.licensing.status import LicenseStatus
from app.shared.datetimes import now_pkt

logger = logging.getLogger(__name__)

# Qt takes a 32-bit millisecond interval, so a licence expiring in a year
# cannot be armed in one go — `QTimer.start()` raises OverflowError past
# 2**31-1. Long waits are served a day at a time; each one re-evaluates,
# which costs a file read. This is not polling: once the next transition
# is inside a day, the timer is armed at that exact instant.
_MAX_DELAY_MS = 24 * 60 * 60 * 1000

# A floor, so a transition a fraction of a millisecond away cannot arm a
# zero-delay timer, and a wake-up that lands a hair early simply looks
# again a second later instead of spinning.
_MIN_DELAY_MS = 1000


class LicenseWatcher(QObject):
    """Holds the current verdict, and moves it on when the clock does.

    One per run. Both licence screens and the startup gate read this
    rather than the manager directly, so there is a single answer on
    screen at any moment and a renewal entered on the Licence page
    reschedules the app as a whole.
    """

    stateChanged = Signal(object)  # LicenseState, on every re-evaluation

    def __init__(
        self,
        manager: LicenseManager,
        *,
        expiring_soon_days: int,
        clock: Callable[[], datetime] = now_pkt,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._expiring_soon_days = expiring_soon_days
        self._clock = clock
        self._next_at: datetime | None = None
        # Which situations have already been put in front of the user this
        # run — keyed on (status, in_grace), the three the shop is warned
        # about being expiring, expired-in-grace and expired-blocked.
        self._announced: set[tuple[LicenseStatus, bool]] = set()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.check)

        app = QApplication.instance()
        if app is not None:
            # Coming back to the app is the other moment worth looking:
            # a machine that slept through an expiry wakes with a timer
            # that fired late or not at all.
            app.applicationStateChanged.connect(self._on_application_state)

    @property
    def manager(self) -> LicenseManager:
        """For the two operations that change the licence rather than read
        it — activation and deactivation, both of which belong to the view
        model and are followed by a `check()`."""
        return self._manager

    def state(self) -> LicenseState:
        """The verdict as last evaluated. Cheap, and safe to ask often."""
        return self._manager.state()

    def next_transition_at(self) -> datetime | None:
        """When the timer is currently set for, or `None` when nothing is
        counting down. The scheduled instant itself, not the clamped
        wake-up used to reach it."""
        return self._next_at

    def check(self) -> LicenseState:
        """Re-read the licence, reschedule, and tell everyone.

        The single entry point: startup, the timer, activation, renewal,
        and the app or its window being activated all come through here.
        """
        state = self._manager.refresh()
        self._reschedule(state)
        self.stateChanged.emit(state)
        return state

    def take_notice(self) -> LicenseState | None:
        """The current verdict if the shop has not been told about it yet
        this run, otherwise `None`.

        Asked by whatever can actually show a message, so a transition
        that happens while no window is up is still announced when one
        opens — and signing out and back in does not repeat a warning
        already given. Expiring, expired-but-trading and locked out are
        three different things to tell a shop, so each is told once; a
        licence in order carries no message and says nothing at all.
        """
        state = self.state()
        if state.message is None:
            return None
        situation = (state.status, state.in_grace)
        if situation in self._announced:
            return None
        self._announced.add(situation)
        return state

    # ---------------- scheduling ----------------

    def _reschedule(self, state: LicenseState) -> None:
        self._timer.stop()
        now = self._clock()
        self._next_at = next_transition_at(
            state, now=now, expiring_soon_days=self._expiring_soon_days
        )
        if self._next_at is None:
            return

        wait = (self._next_at - now).total_seconds() * 1000
        delay = max(_MIN_DELAY_MS, min(int(wait), _MAX_DELAY_MS))
        logger.debug("Next licence transition at %s; waking in %sms", self._next_at, delay)
        self._timer.start(delay)

    def _on_application_state(self, app_state: Qt.ApplicationState) -> None:
        if app_state is Qt.ApplicationState.ApplicationActive:
            self.check()
