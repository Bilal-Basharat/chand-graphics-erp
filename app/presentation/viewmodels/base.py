"""
Common view model plumbing: busy state, non-blocking use-case execution,
and one shared exception -> user-facing message mapping.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from app.application.auth.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InactiveAccountError,
    InvalidCredentialsError,
    LoginThrottledError,
)
from app.application.exceptions import ApplicationError
from app.presentation.services.async_runner import AsyncTaskRunner

logger = logging.getLogger(__name__)


class BaseViewModel(QObject):
    """
    Base class for every screen's view model.

    Views connect to `busyChanged`/`errorOccurred` and otherwise only see
    the concrete state signals/properties each subclass adds. No view
    model here or in a subclass ever imports a PySide6 widget class.
    """

    busyChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, runner: AsyncTaskRunner | None = None) -> None:
        super().__init__()
        self._runner = runner or AsyncTaskRunner()
        self._busy = False

    @property
    def busy(self) -> bool:
        return self._busy

    def _set_busy(self, value: bool) -> None:
        if self._busy == value:
            return
        self._busy = value
        self.busyChanged.emit(value)

    def run_async(
        self,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
    ) -> None:
        """
        Execute `fn` (a use-case call) off the UI thread.

        On success, `on_success(result)` runs on the main thread.
        On failure, the exception is mapped to a friendly message and
        emitted via `errorOccurred` — callers do not need their own
        try/except around use-case calls.
        """
        self._set_busy(True)

        def _on_success(result: Any) -> None:
            self._set_busy(False)
            if on_success is not None:
                on_success(result)

        def _on_error(exc: Exception) -> None:
            self._set_busy(False)
            self.errorOccurred.emit(self._friendly_message(exc))

        self._runner.run(fn, on_success=_on_success, on_error=_on_error)

    @staticmethod
    def _friendly_message(exc: Exception) -> str:
        # Sign-in failures already carry an accurate, user-facing reason
        # ("Invalid email or password", "This account is inactive", "Too
        # many failed sign-in attempts…"). Collapsing them into a generic
        # line loses the one thing the user needs — most damagingly for a
        # lockout, where "please sign in again" is the opposite of true.
        if isinstance(exc, (InvalidCredentialsError, InactiveAccountError, LoginThrottledError)):
            return str(exc)
        # A session that expired mid-use, on the other hand, really does
        # just need signing in again.
        if isinstance(exc, AuthenticationError):
            return "Your session has ended. Please sign in again."
        if isinstance(exc, AuthorizationError):
            return "You don't have permission to do this."
        if isinstance(exc, (ApplicationError, ValueError)):
            return str(exc)
        logger.error("Unexpected error in view model", exc_info=exc)
        return "Something went wrong. Please try again."
