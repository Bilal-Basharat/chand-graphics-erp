"""
One copy of this application per computer.

A second copy is not a harmless duplicate. Both open the same SQLite
file, and SQLite takes the write lock per connection — so the two meet
"database is locked" at the moment somebody presses Save, and until then
they disagree about what has been entered, because neither sees the
other's uncommitted work. Two windows also means two sets of unsaved
work, and one of them is going to be closed by the person who thinks
they are looking at the other.

A user does not set out to do this. They double-click the desktop icon
again because the first launch is still starting, or because the window
is behind the browser. So the second copy does not open: it puts the
running one back in front and exits, which is what the click meant.

The lock is a `QLockFile`, which records the process holding it. That is
what makes a crash survivable — a copy killed by a power cut leaves a
lock the next launch reclaims, rather than a machine that can never open
the application again — and it is what this module reads to find the
window to raise. By process id, deliberately: the window title changes
with the screen the user is on, and the executable is `python.exe` when
this is run from a checkout, which would match any other Python window
on the machine and raise a stranger's application.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QLockFile

_WAIT_MS = 100
"""How long to wait for the lock before concluding somebody else has it.
Long enough to cross a filesystem, short enough that a user who is
already double-clicking sees no pause."""

_SW_RESTORE = 9
_GW_OWNER = 4

_ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class SingleInstance:
    """The lock this copy runs under, and the window it points at."""

    def __init__(self, lock_path: Path) -> None:
        # Normally already there — the data folder beside it is created at
        # import time — but `ERP_DATA_DIR` can move that elsewhere. A lock
        # file that cannot be created fails to lock, which would read as
        # "another copy is running" and exit without ever showing a window.
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(lock_path))
        # No age-based staleness: a copy that is merely slow — a first run
        # migrating a database, say — must never have its lock taken from
        # under it. A copy that has actually died is spotted by its process
        # id being gone, which QLockFile checks whatever this is set to.
        self._lock.setStaleLockTime(0)

    def acquire(self) -> bool:
        """Take the lock, or report that another copy is holding it."""
        return self._lock.tryLock(_WAIT_MS)

    def release(self) -> None:
        self._lock.unlock()

    def activate_existing_instance(self) -> bool:
        """Bring the copy that holds the lock back to the front.

        Best-effort and Windows-only: it is a courtesy on the way out, not
        something the decision to exit depends on. False means there was
        nothing to raise — the other copy is still starting and has no
        window yet, or has just let the lock go.
        """
        if os.name != "nt":
            return False

        # Zero when there is no lock file to read — which happens if the
        # holder released it in the moment between the failed attempt and
        # this call.
        pid, _hostname, _appname = self._lock.getLockInfo()
        if not pid:
            return False

        window = _main_window(pid)
        if window is None:
            return False

        user32 = _user32()
        # Restores a minimised window, and does no harm to one that isn't.
        #
        # The *async* form on purpose: `ShowWindow` on another process's
        # window waits for that process to handle the message, so a
        # running copy that is busy or wedged would take this one down
        # with it — and the user would be left with no window at all
        # rather than a slow one. Posting it cannot hang.
        user32.ShowWindowAsync(window, _SW_RESTORE)
        # Whether the window also gets the keyboard is Windows' to decide:
        # a process may only hand the foreground on while it holds it,
        # which a copy launched from the desktop icon does and one
        # launched from a script may not. Refused, the restore above still
        # lands and the window is on screen — so the answer here is "there
        # was a window and it was asked to come forward", which is the
        # part this can actually know.
        user32.SetForegroundWindow(window)
        return True


@lru_cache(maxsize=1)
def _user32():
    """The handful of window calls this needs, with their signatures.

    Declared rather than left to ctypes' defaults: a window handle is
    pointer-sized, and a return value assumed to be a C `int` is a handle
    with its top half cut off on 64-bit Windows.
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumWindows.argtypes = [_ENUM_PROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindowAsync.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    return user32


def _main_window(pid: int) -> int | None:
    """The application window belonging to process `pid`, if it has one.

    Owned windows are passed over so that a message box does not stand in
    for the shell behind it — raising the shell brings its dialog along
    anyway, and raising the dialog alone leaves the window the user was
    looking for still buried.

    None is an ordinary answer: the other copy may be part-way through
    starting and have nothing on screen yet.
    """
    user32 = _user32()
    found: int | None = None

    @_ENUM_PROC
    def visit(window: int, _lparam: int) -> bool:
        nonlocal found
        if user32.GetWindow(window, _GW_OWNER) or not user32.IsWindowVisible(window):
            return True

        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(window, ctypes.byref(window_pid))
        if window_pid.value != pid:
            return True

        found = window
        return False  # stop the enumeration

    user32.EnumWindows(visit, 0)
    return found
