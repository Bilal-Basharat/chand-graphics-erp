from __future__ import annotations

from PySide6.QtCore import Signal

from app.config.settings import AppSettings
from app.domain.licensing.ports import InstallationIdentity
from app.presentation.license_watch import LicenseWatcher
from app.presentation.support import support_details, support_line
from app.presentation.viewmodels.base import BaseViewModel


class LicenseViewModel(BaseViewModel):
    """Backs the activation dialog and the licence screen.

    Takes the watcher rather than the container: licensing is the one
    thing that has to work before the container's other half — a
    database, a signed-in user — means anything, and the startup gate
    builds this view model when neither exists yet.

    The watcher, rather than the manager, because it holds the one verdict
    the whole app is running on. Every screen built on this therefore
    shows the same answer at the same moment, including when the licence
    changes underneath it, and no screen works expiry out for itself.
    """

    stateChanged = Signal(object)  # LicenseState, whenever the verdict is re-read
    activated = Signal(object)  # LicenseState, only after a key entered here was taken

    def __init__(
        self,
        watcher: LicenseWatcher,
        identity: InstallationIdentity,
        settings: AppSettings,
    ) -> None:
        super().__init__()
        self._watcher = watcher
        self._identity = identity
        self._settings = settings
        self._watcher.stateChanged.connect(self.stateChanged.emit)

    @property
    def installation_id(self) -> str:
        """Read synchronously: the dialog shows it the moment it opens,
        and it is a single small file read."""
        return self._identity.installation_id()

    @property
    def support_details(self) -> list[tuple[str, str]]:
        """Who to call for a key, a fault or a change to the app."""
        return support_details(self._settings)

    @property
    def support_line(self) -> str:
        """The same, on one line, for the activation dialog's footer."""
        return support_line(self._settings)

    def load(self) -> None:
        """The verdict already in hand. Synchronous — it has been read."""
        self.stateChanged.emit(self._watcher.state())

    def activate(self, license_key: str) -> None:
        """A rejected key arrives back through `errorOccurred`, carrying
        the reason it was refused.

        An accepted one is announced on `activated` as well as on
        `stateChanged`, and the difference is the point: `stateChanged`
        also fires for the clock, so it says what the licence is now, not
        that anybody did anything. Only a screen that asked for this can
        close itself on the answer.
        """
        self.run_async(
            lambda: self._watcher.manager.activate(license_key),
            # `check()` arms a timer, so it must run on the UI thread —
            # which is where `on_success` is delivered. It re-reads what
            # was just written, so what is scheduled is what is on disk,
            # and its verdict is the one reported back.
            on_success=lambda _state: self.activated.emit(self._watcher.check()),
        )

    def deactivate(self) -> None:
        self.run_async(
            self._watcher.manager.deactivate,
            on_success=lambda _result: self._watcher.check(),
        )
