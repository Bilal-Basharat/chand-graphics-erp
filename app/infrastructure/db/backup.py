"""Taking a copy of the customer's database, on demand.

Written for the one place that needs it today — a shop whose licence has
lapsed must still be able to get its own data out — and deliberately
general enough to be the backup feature when one is wanted.

Uses SQLite's own online backup rather than copying the file. A plain
copy of a database with a connection open to it can land mid-transaction
and produce a file that opens and is wrong, which is the worst possible
outcome for something the shop will only look at on the day it has lost
everything else.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from app.config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)


def backup_database(destination: Path, *, source: Path = DATABASE_PATH) -> Path:
    """Write a consistent copy of the database to `destination`.

    Returns:
        The path written.

    Raises:
        FileNotFoundError: If there is no database to copy yet.
        sqlite3.Error: If the copy could not be completed.
    """
    if not source.exists():
        raise FileNotFoundError(f"There is no database at {source} to back up.")

    destination.parent.mkdir(parents=True, exist_ok=True)

    # `closing`, not sqlite3's own context manager: that one commits the
    # transaction and leaves the connection — and on Windows its open
    # handle — very much alive.
    with (
        closing(sqlite3.connect(source)) as connection,
        closing(sqlite3.connect(destination)) as copy,
    ):
        connection.backup(copy)

    logger.info("Backed up the database to %s", destination)
    return destination
