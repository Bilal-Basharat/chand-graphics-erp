"""
Owns which window is on screen: the sign-in screen or the application
shell, and the transitions between them.

This exists because signing out is not just "call the use case". The
shell has to come down in a specific order, or teardown produces errors
the user can't act on:

1. Hide the shell first. Its screens reload on `showEvent` and refresh on
   navigation; if the session were cleared while it was still visible,
   those queries would fail authentication and raise warning dialogs
   during sign-out.
2. Let in-flight background queries finish. Results are delivered back by
   queued signal, and delivering one into a half-destroyed window is how
   this crashes rather than merely misbehaves.
3. Only then clear the session and swap in the sign-in screen.

The replacement window is also always shown *before* the outgoing one is
closed. Qt quits the application when the last visible window closes, so
closing first would exit during the handover — while still letting a user
who closes the window themselves quit normally, which is what they meant.

Keeping that sequence in one place also means `bootstrap()` stays a
composition root rather than growing window-lifecycle logic.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThreadPool

from app.container import AppContainer
from app.presentation.dialogs.confirm import confirm_destructive
from app.presentation.license_watch import LicenseWatcher
from app.presentation.viewmodels.session_viewmodel import SessionViewModel
from app.presentation.views.login_view import LoginView
from app.presentation.windows.main_window import MainWindow

logger = logging.getLogger(__name__)

# Local SQLite queries finish in milliseconds; this is a ceiling for a
# pathological case, not an expected wait.
_DRAIN_TIMEOUT_MS = 3000


class SessionController(QObject):
    def __init__(
        self,
        container: AppContainer,
        watcher: LicenseWatcher,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._container = container
        # Passed through rather than built here: it outlives every shell,
        # so a warning already given is not repeated after a sign-out.
        self._watcher = watcher
        self._session_view_model = SessionViewModel(container)
        self._login: LoginView | None = None
        self._shell: MainWindow | None = None
        self._signing_out = False

        self._session_view_model.signedOut.connect(self._on_signed_out)
        # Without this a failed sign-out would emit only errorOccurred,
        # signedOut would never fire, and the user would be left with a
        # hidden shell and no window at all — the app looking as though it
        # had vanished. Whatever went wrong, the sign-in screen is the
        # right place to end up.
        self._session_view_model.errorOccurred.connect(self._on_sign_out_failed)

    def start(self) -> None:
        """Open whichever window the restored session calls for."""
        if self._session_view_model.is_authenticated():
            self._show_shell()
        else:
            self._show_login()

    # ---------------- windows ----------------

    def _show_login(self) -> None:
        login = LoginView(self._session_view_model)
        login.signedIn.connect(self._on_signed_in)
        self._login = login
        login.show()
        login.raise_()
        login.activateWindow()

    def _show_shell(self) -> None:
        shell = MainWindow(self._container, self._session_view_model, self._watcher)
        shell.signOutRequested.connect(self.sign_out)
        self._shell = shell
        shell.show()
        shell.raise_()
        shell.activateWindow()

    def _close_login(self) -> None:
        if self._login is None:
            return
        self._login.close()
        self._login.deleteLater()
        self._login = None

    def _close_shell(self) -> None:
        if self._shell is None:
            return
        shell, self._shell = self._shell, None
        shell.close()
        # deleteLater, not immediate destruction: any signal already queued
        # for this window is delivered before the object goes away.
        shell.deleteLater()

    @staticmethod
    def _drain_background_work() -> None:
        if not QThreadPool.globalInstance().waitForDone(_DRAIN_TIMEOUT_MS):
            logger.warning(
                "Background queries still running after %sms; continuing sign-out",
                _DRAIN_TIMEOUT_MS,
            )

    # ---------------- transitions ----------------

    def _on_signed_in(self, _user) -> None:
        self._show_shell()
        self._close_login()

    def sign_out(self) -> None:
        # Signing out discards whatever the user was part-way through, and
        # is only recoverable by signing back in — worth one confirmation.
        #
        # Asked through the app's own helper rather than
        # QMessageBox.question: that returns the clicked button as a plain
        # int across the PySide6 boundary, so comparing it by identity to
        # StandardButton.Yes was never true and sign-out silently did
        # nothing. `confirm_destructive` compares the button objects
        # themselves, and names the two outcomes besides.
        if not confirm_destructive(
            self._shell,
            title="Sign out",
            message="Sign out of Chand Graphics?\n\nAnything you haven't saved will be lost.",
            confirm_label="Sign out",
            cancel_label="Stay signed in",
        ):
            return

        if self._shell is not None:
            # Hidden, not closed: its screens reload whenever they're shown,
            # and those queries would fail against a cleared session. Closing
            # is deferred until the sign-in window is up (see module docstring).
            self._shell.hide()
        self._signing_out = True
        self._drain_background_work()
        self._session_view_model.sign_out()

    def _on_signed_out(self) -> None:
        self._signing_out = False
        self._show_login()
        self._close_shell()

    def _on_sign_out_failed(self, message: str) -> None:
        if not self._signing_out:
            # An error from some other session operation (a sign-in
            # attempt, say) — the screen that asked for it reports it.
            return
        logger.error("Sign-out did not complete cleanly: %s", message)
        self._signing_out = False
        self._show_login()
        self._close_shell()
