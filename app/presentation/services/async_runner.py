"""
Runs synchronous work (use-case calls hitting SQLAlchemy/SQLite) off the
Qt main thread, so the UI never freezes while a query or write is in flight.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

logger = logging.getLogger(__name__)


class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(Exception)


class _Worker(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:  # noqa: BLE001 - forwarded to the caller's error handler
            logger.debug("Background task failed", exc_info=True)
            self.signals.failed.emit(exc)
        else:
            self.signals.succeeded.emit(result)


class AsyncTaskRunner:
    """
    Fire-and-forget helper: run `fn` on a thread pool, deliver the outcome
    back on the calling (Qt main) thread via `on_success`/`on_error`.

    Intended to be used by BaseViewModel.run_async, not called directly
    by views.
    """

    def __init__(self, thread_pool: QThreadPool | None = None) -> None:
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        # QRunnable is not a QObject, so nothing keeps its Python wrapper (or
        # the signals QObject it owns) alive once run() returns control to
        # the caller. Without this, Qt's C++-side ownership of the queued
        # QRunnable does not stop the Python side from being garbage
        # collected mid-flight, which segfaults on cross-thread signal
        # delivery. Keep a strong reference until the worker reports done.
        self._active: set[_Worker] = set()

    def run(
        self,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        worker = _Worker(fn)
        if on_success is not None:
            worker.signals.succeeded.connect(on_success)
        if on_error is not None:
            worker.signals.failed.connect(on_error)

        worker.signals.succeeded.connect(lambda _result, w=worker: self._active.discard(w))
        worker.signals.failed.connect(lambda _exc, w=worker: self._active.discard(w))

        self._active.add(worker)
        self._thread_pool.start(worker)
