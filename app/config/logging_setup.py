"""
Where log records go.

Every module in this application logs — `logger.exception` on a failed
save, `logger.error` on schema drift, `logger.warning` on an unreadable
preferences file. Until this ran, none of it went anywhere: with no
handler configured, Python drops records below WARNING and prints the
rest to stderr, which a windowed build does not have. A customer
reporting "it just closed" left nothing behind to read.

So: one rotating file, in the installation's own `logs/` folder, plus the
console while developing. Rotation is what keeps a machine that has been
running for two years from filling a disk with one enormous file.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config.paths import IS_FROZEN, LOG_FILE_PATH

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def configure_logging(level: int = logging.INFO, path: Path = LOG_FILE_PATH) -> None:
    """Attach the application's log handlers, once.

    Called first thing at startup, before anything that might log. Does
    nothing if handlers are already attached, so a test or a script that
    has configured its own logging keeps it.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)

    file_handler = _file_handler(path)
    if file_handler is not None:
        root.addHandler(file_handler)

    # In a packaged build there is no console to write to, and stderr may
    # not even be a real stream — but if the log file could not be opened,
    # a stream handler is still better than discarding the records.
    if not IS_FROZEN or file_handler is None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(console)


def _file_handler(path: Path) -> RotatingFileHandler | None:
    """The rotating log file, or nothing if it cannot be written.

    A folder that is read-only, full, or held open by a backup tool is a
    reason to lose the log — never a reason to stop the application
    starting.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None

    handler.setFormatter(logging.Formatter(_FORMAT))
    return handler
