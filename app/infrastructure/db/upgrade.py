"""
Bringing an installation that already holds data up to this build.

Two things can be stale about a database this app is handed: where it
sits, and what shape its tables are in. Both are settled here, once, at
startup, before anything reads from it.

`create_all()` is not a migration tool. It creates tables that are
missing and looks at nothing else — a column added to a model never
appears, and a column dropped from one stays behind with whatever
constraints it had. That is not a theoretical gap: dropping the price
columns from cards and inventory items left them NOT NULL in every
database already in the field, so every new card failed to insert while
the existing rows read back perfectly.

Schema steps are numbered by SQLite's own `user_version`, so a database
carries its own position in the list and nothing else has to be tracked.
Each step is written to be safe to run twice — a database in a
half-applied state converges rather than failing.
"""
from __future__ import annotations

import logging
import shutil
from collections.abc import Callable

from sqlalchemy import Connection, Engine

from app.config.settings import DATA_DIR, DATABASE_PATH, legacy_data_dirs

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- data


def adopt_previous_installation() -> None:
    """Carry an earlier build's data folder over to this one.

    Runs only when this installation has no database yet and an older one
    does, so it happens once and never overwrites live data. The original
    is copied rather than moved: if anything about this build goes wrong,
    the customer's fortnight of trading is still sitting where it was.
    """
    if DATABASE_PATH.exists():
        return

    for previous in legacy_data_dirs():
        if previous == DATA_DIR or not (previous / DATABASE_PATH.name).exists():
            continue
        logger.info("Adopting data from previous installation at %s", previous)
        shutil.copytree(previous, DATA_DIR, dirs_exist_ok=True)
        return


# -------------------------------------------------------------- schema


def _table_columns(connection: Connection, table: str) -> set[str]:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _drop_columns(connection: Connection, table: str, columns: tuple[str, ...]) -> None:
    """Drop columns if this database still has them.

    SQLite has supported DROP COLUMN since 3.35 (2021); every Python this
    app can run on ships far newer.
    """
    present = _table_columns(connection, table)
    for column in columns:
        if column in present:
            logger.info("Dropping %s.%s", table, column)
            connection.exec_driver_sql(f"ALTER TABLE {table} DROP COLUMN {column}")


def _drop_catalogue_prices(connection: Connection) -> None:
    """Prices moved onto the transactions that set them.

    A card is bought and sold at different prices over time, so a single
    price on the catalogue record only ever recorded the most recent one.
    The columns are gone from the models; left behind in the file they are
    NOT NULL with no default, and every insert fails on them.
    """
    for table in ("cards", "inventory_items"):
        _drop_columns(connection, table, ("purchase_price", "selling_price"))


_STEPS: tuple[Callable[[Connection], None], ...] = (
    _drop_catalogue_prices,
)
"""Ordered, append-only. A step's position is its version, so never
reorder or remove one — a database in the field records how far down this
list it has come."""


def _backup(version: int) -> None:
    """One copy of the file before it is altered, kept alongside it.

    Cheap, and the difference between a bad migration being an
    inconvenience and being the end of a customer's records.
    """
    backup = DATABASE_PATH.with_suffix(f".v{version}.backup")
    if DATABASE_PATH.exists() and not backup.exists():
        shutil.copy2(DATABASE_PATH, backup)
        logger.info("Backed up the database to %s before migrating", backup.name)


def migrate(engine: Engine) -> None:
    """Apply every schema step this database has not seen yet."""
    with engine.begin() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
        pending = _STEPS[version:]

        if pending:
            _backup(version)
            for step in pending:
                step(connection)

        if version != len(_STEPS):
            # Not parameterisable — PRAGMA takes a literal. The value is
            # the length of a tuple defined above, never external input.
            connection.exec_driver_sql(f"PRAGMA user_version = {len(_STEPS)}")
