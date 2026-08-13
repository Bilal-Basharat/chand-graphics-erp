from __future__ import annotations

from PySide6.QtCore import Signal

from app.application.licensing.manager import LicenseManager
from app.domain.licensing.ports import InstallationIdentity
from app.presentation.viewmodels.base import BaseViewModel


class LicenseViewModel(BaseViewModel):
    """Backs the activation dialog and the licence screen.

    Takes the manager rather than the container: licensing is the one
    thing that has to work before the container's other half — a
    database, a signed-in user — means anything, and the startup gate
    builds this view model when neither exists yet.
    """

    stateChanged = Signal(object)  # LicenseState

    def __init__(self, manager: LicenseManager, identity: InstallationIdentity) -> None:
        super().__init__()
        self._manager = manager
        self._identity = identity

    @property
    def installation_id(self) -> str:
        """Read synchronously: the dialog shows it the moment it opens,
        and it is a single small file read."""
        return self._identity.installation_id()

    def load(self) -> None:
        self.run_async(self._manager.state, on_success=self.stateChanged.emit)

    def refresh(self) -> None:
        self.run_async(self._manager.refresh, on_success=self.stateChanged.emit)

    def activate(self, license_key: str) -> None:
        """A rejected key arrives back through `errorOccurred`, carrying
        the reason it was refused."""
        self.run_async(
            lambda: self._manager.activate(license_key),
            on_success=self.stateChanged.emit,
        )

    def deactivate(self) -> None:
        def _deactivate():
            self._manager.deactivate()
            return self._manager.state()

        self.run_async(_deactivate, on_success=self.stateChanged.emit)
