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


def _relax_payment_method_links(connection: Connection) -> None:
    """Payment method became optional on a payment.

    Two changes to the same column, neither of which SQLite can make in
    place: it stops being NOT NULL, and it gains ON DELETE SET NULL so a
    method that is deleted leaves the payments it settled intact rather
    than being undeletable. SQLite's own answer to both is to rebuild the
    table, which is what this does.

    Safe to rerun: a database already rebuilt has a nullable column and is
    skipped.
    """
    for table, document_column, document_table, user_column, timestamp in (
        ("sale_payments", "sale_id", "sales", "received_by_user_id", "received_at"),
        ("purchase_payments", "purchase_id", "purchases", "paid_by_user_id", "paid_at"),
    ):
        if _is_nullable(connection, table, "payment_method_id"):
            continue

        logger.info("Rebuilding %s so its payment method is optional", table)
        columns = (
            f"id, {document_column}, payment_method_id, amount, reference_no, note, "
            f"{user_column}, {timestamp}, created_at, updated_at"
        )
        connection.exec_driver_sql(
            f"""
            CREATE TABLE {table}_rebuilt (
                id INTEGER NOT NULL,
                {document_column} INTEGER NOT NULL,
                payment_method_id INTEGER,
                amount NUMERIC(12, 2) NOT NULL,
                reference_no VARCHAR(100),
                note VARCHAR(500),
                {user_column} INTEGER NOT NULL,
                {timestamp} DATETIME NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME,
                PRIMARY KEY (id),
                FOREIGN KEY({document_column}) REFERENCES {document_table} (id),
                FOREIGN KEY(payment_method_id) REFERENCES payment_methods (id) ON DELETE SET NULL,
                FOREIGN KEY({user_column}) REFERENCES users (id)
            )
            """
        )
        connection.exec_driver_sql(
            f"INSERT INTO {table}_rebuilt ({columns}) SELECT {columns} FROM {table}"
        )
        connection.exec_driver_sql(f"DROP TABLE {table}")
        connection.exec_driver_sql(f"ALTER TABLE {table}_rebuilt RENAME TO {table}")
        # The indexes belonged to the table that was just dropped, so they
        # went with it and are recreated here rather than left missing.
        for column in (document_column, "payment_method_id", user_column, "created_at"):
            connection.exec_driver_sql(
                f"CREATE INDEX ix_{table}_{column} ON {table} ({column})"
            )


def _is_nullable(connection: Connection, table: str, column: str) -> bool:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column and not row[3] for row in rows)


def _table_exists(connection: Connection, table: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _add_column(connection: Connection, table: str, column: str, definition: str) -> None:
    """Add a column if this database has not got it yet."""
    if column in _table_columns(connection, table):
        return
    logger.info("Adding %s.%s", table, column)
    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _rebuild_to_match_model(connection: Connection, table: str, carried: tuple[str, ...]) -> None:
    """Recreate a table from its model, carrying `carried` across.

    SQLite will not drop a column that an index or a CHECK constraint
    names, and both stood in the way of dropping `card_id`. Its own answer
    is to rebuild the table — done here from `Base.metadata` rather than
    from hand-written DDL, so the result is exactly the table the rest of
    this build expects rather than a second description of it that can
    drift.
    """
    from app.infrastructure.db.base import Base

    logger.info("Rebuilding %s to match its model", table)
    # The old table's indexes keep their names through the rename, and
    # would collide with the ones the new table creates.
    for (index,) in connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ? "
        "AND sql IS NOT NULL",
        (table,),
    ).fetchall():
        connection.exec_driver_sql(f"DROP INDEX {index}")

    connection.exec_driver_sql(f"ALTER TABLE {table} RENAME TO {table}_old")
    Base.metadata.tables[table].create(bind=connection)
    columns = ", ".join(carried)
    connection.exec_driver_sql(
        f"INSERT INTO {table} ({columns}) SELECT {columns} FROM {table}_old"
    )
    connection.exec_driver_sql(f"DROP TABLE {table}_old")


_LINE_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "sale_items",
        (
            "id", "sale_id", "item_type", "inventory_item_id", "quantity", "unit_price",
            "discount_amount", "line_total", "previous_stock", "resulting_stock", "note",
            "created_at", "updated_at",
        ),
    ),
    (
        "purchase_items",
        (
            "id", "purchase_id", "item_type", "inventory_item_id", "quantity", "unit_price",
            "discount_amount", "line_total", "previous_stock", "resulting_stock", "note",
            "created_at", "updated_at",
        ),
    ),
    (
        "inventory_movements",
        (
            "id", "movement_type", "item_type", "inventory_item_id", "source_document_type",
            "source_document_id", "quantity", "unit_price", "previous_stock",
            "resulting_stock", "reference_no", "reason", "note", "occurred_at",
            "created_by_user_id", "updated_by_user_id", "created_at", "updated_at",
        ),
    ),
)
"""Every table that carried a `card_id`, and what survives the rebuild."""


def _fold_cards_into_inventory(connection: Connection) -> None:
    """Wedding cards stop being a module of their own and become stock.

    The app trades in one kind of item now, so each card becomes an
    inventory item under the cabinet it was filed in, and every sale line,
    purchase line and stock movement that named a card is repointed at it.
    Nothing is deleted: a shop's trading history reads exactly as it did,
    under the item's new name.

    The `cards` table itself is left where it is rather than dropped.
    Databases in the field still carry tables from features removed before
    this one — `job_materials` among them — which no model describes and
    no code reads, and one of them holds a row pointing at a card. Dropping
    `cards` would mean deleting that row first, which is a decision about
    somebody else's data and not this step's to make. An unread table costs
    nothing; the columns that pointed at it are gone either way.

    Safe to rerun: a database whose line tables have no `card_id` left has
    already been through this, and only the cabinet column is reapplied —
    guarded in its own right.
    """
    _add_column(connection, "inventory_items", "cabinet_id", "INTEGER REFERENCES cabinets(id)")
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_inventory_items_cabinet_id "
        "ON inventory_items (cabinet_id)"
    )

    if not _table_exists(connection, "cards") or "card_id" not in _table_columns(
        connection, "sale_items"
    ):
        return

    taken = {
        name for (name,) in connection.exec_driver_sql("SELECT name FROM inventory_items")
    }
    cards = connection.exec_driver_sql(
        "SELECT id, card_number, name, current_stock, minimum_stock, description, "
        "cabinet_id, created_by_user_id, updated_by_user_id, created_at, updated_at "
        "FROM cards"
    ).fetchall()

    for card in cards:
        card_id, card_number, name = card[0], card[1], card[2]
        item_name = _free_name(f"{card_number} — {name}" if name else str(card_number), taken)
        taken.add(item_name)

        result = connection.exec_driver_sql(
            "INSERT INTO inventory_items (name, current_stock, minimum_stock, description, "
            "cabinet_id, unit, created_by_user_id, updated_by_user_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)",
            (item_name, *card[3:]),
        )
        logger.info("Card '%s' is now inventory item '%s'", card_number, item_name)

        for table, _columns in _LINE_TABLES:
            # `card_id` is cleared in the same statement, not left for the
            # rebuild below: while it is still there, the exclusive-arc
            # CHECK these tables carry refuses a row naming both.
            connection.exec_driver_sql(
                f"UPDATE {table} SET inventory_item_id = ?, card_id = NULL, "
                "item_type = 'INVENTORY_ITEM' WHERE card_id = ?",
                (result.lastrowid, card_id),
            )

    for table, columns in _LINE_TABLES:
        _rebuild_to_match_model(connection, table, columns)


def _free_name(wanted: str, taken: set[str]) -> str:
    """`wanted`, or the first numbered variant of it nothing else holds.

    Item names are unique, and a card's number is not guaranteed to be
    free among items that were already there.
    """
    if wanted not in taken:
        return wanted
    suffix = 2
    while f"{wanted} ({suffix})" in taken:
        suffix += 1
    return f"{wanted} ({suffix})"


def _add_party_opening_balance(connection: Connection) -> None:
    """Parties carry a balance from before the software was installed.

    Nothing in the database can tell us what a customer already owed on the
    day the shop started using this, so it is entered by hand and stored.
    Existing rows take the default of zero, which is what they meant
    before the column existed.
    """
    for table in ("customers", "suppliers"):
        _add_column(connection, table, "opening_balance", "NUMERIC(12, 2) NOT NULL DEFAULT 0")


_STEPS: tuple[Callable[[Connection], None], ...] = (
    _drop_catalogue_prices,
    _relax_payment_method_links,
    _fold_cards_into_inventory,
    _add_party_opening_balance,
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
