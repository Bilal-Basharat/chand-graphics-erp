"""Whether this installation may open at all.

Sits at startup, between "Qt is configured" and "show the sign-in
window", and nowhere else. Licensing is a property of the installation,
not of a sale or a stock movement, so it is decided once here rather than
asked again inside business code that has no opinion about it — which is
also what keeps the licensing layer removable, replaceable and testable
on its own.

Held to one job: say yes, or put the activation dialog in front of the
user and say whatever they decide. `bootstrap()` stays a composition
root, exactly as it does for `SessionController`.
"""
from __future__ import annotations

import logging

from app.container import AppContainer
from app.presentation.dialogs.activation_dialog import ActivationDialog
from app.presentation.viewmodels.license_viewmodel import LicenseViewModel

logger = logging.getLogger(__name__)


class LicenseGate:
    def __init__(self, container: AppContainer) -> None:
        self._container = container

    def ensure_licensed(self) -> bool:
        """True when the app may go on to sign-in.

        Read synchronously: a file and one signature check, and there is
        no window yet to keep responsive.
        """
        manager = self._container.license_manager()
        state = manager.state()

        if state.is_usable:
            if state.message:
                # Expiring, or expired and inside its grace window. The
                # licence screen shows this properly; the log is what a
                # support call has to go on.
                logger.warning("Licence notice: %s", state.message)
            return True

        logger.warning("Licence check failed: %s", state.message)

        dialog = ActivationDialog(
            LicenseViewModel(manager, self._container.installation_identity()),
            state=state,
            blocked=True,
        )
        dialog.exec()

        # Asked of the manager rather than taken from the dialog's exit
        # code: the manager is what the rest of the app will read, and a
        # dialog closed by the window's X button has no result to give.
        return manager.state().is_usable
