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
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import Connection, Engine

from app.config.paths import (
    DATA_DIR,
    DATABASE_PATH,
    INSTALLATION_STATE_FILES,
    legacy_data_dirs,
    previous_database,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- data


def adopt_previous_installation() -> None:
    """Carry an earlier build's data folder over to this one.

    Runs only when this installation has no database yet and an older one
    does, so it happens once and never overwrites live data. The original
    is copied rather than moved: if anything about this build goes wrong,
    the customer's fortnight of trading is still sitting where it was.

    The licence travels with the database. Without that, every shop in
    the field would meet the activation dialog the first time they opened
    the build that moved the folder.

    The database is recognised by any name this application has ever
    given one, and arrives under the name this build uses — so renaming
    it in some later build is a matter of listing the old name, not of
    leaving a shop's trading behind.
    """
    if DATABASE_PATH.exists():
        return

    for previous in legacy_data_dirs():
        if previous == DATA_DIR:
            continue
        database = previous_database(previous)
        if database is None:
            continue
        logger.info("Adopting data from previous installation at %s", previous)
        _copy_installation_files(previous, DATA_DIR, database)
        return


def _copy_installation_files(source: Path, destination: Path, database: Path) -> None:
    """Copy the files that make up an installation, and only those.

    Named files rather than the whole tree, because one of the folders
    checked is this one's own parent — the arrangement every build before
    this one used. Copying that wholesale would walk into the destination
    while creating it and nest the installation inside itself.

    Left behind deliberately: the generated UI assets in `ui/`, which
    `presentation/theme/assets.py` repaints on demand, and the
    pre-migration `.backup` copies, which stay where they were taken.
    """
    destination.mkdir(parents=True, exist_ok=True)

    # Under this build's name, whatever the file was called where it was
    # found. `DATABASE_PATH` is known not to exist — the caller checked.
    shutil.copy2(database, destination / DATABASE_PATH.name)

    for name in INSTALLATION_STATE_FILES:
        origin = source / name
        target = destination / name
        if origin.is_file() and not target.exists():
            shutil.copy2(origin, target)


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


def _add_index(connection: Connection, table: str, column: str) -> None:
    """Index a column the way `create_all` would have.

    A column added by `ALTER TABLE` gets no index, so a database in the
    field would end up with the columns of a fresh one and none of its
    indexes — the same schema on paper and a different one to query. The
    name is SQLAlchemy's own, so the two files agree on that too.
    """
    connection.exec_driver_sql(
        f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table} ({column})"
    )


def _create_if_missing(connection: Connection, table: str) -> None:
    """Create a table from its model, if this database has not got it.

    For a table this build introduces. `create_all` would make it too, but
    only on the way in to a database that has none of them: a migration
    that assumes its tables are already there is one that fails on the
    first customer to upgrade.
    """
    from app.infrastructure.db.base import Base

    Base.metadata.tables[table].create(bind=connection, checkfirst=True)


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


def _add_sale_line_cost(connection: Connection) -> None:
    """A sale line records what its stock had cost, so margin can be read.

    Without it there is no profit in the database at all: the only
    acquisition cost anywhere is on purchase lines, and nothing connects a
    thing sold to the price it was bought at.

    Nothing in an existing database says what a past sale cost, so it is
    reconstructed the way new sales compute it — the quantity-weighted
    average of every purchase of that item made *on or before the day the
    sale was raised*. Bounded by that date rather than by the whole
    history, because an item bought again this year must not rewrite last
    year's margin. That is the entire reason the figure is stored on the
    line instead of worked out when a report is run.

    Dates come from `purchases`, not from `purchase_items`: a line row
    carries the moment it was written, which for a backdated document is
    not the day it was traded.

    An item that had never been bought has no average, so the subquery
    yields NULL and the column stays NULL. That is not zero and must never
    be read as zero — a sale with no cost is unknown margin, not total
    margin. The reports count these lines and say so.

    Safe to rerun: only rows that still have no cost are touched.
    """
    _add_column(connection, "sale_items", "unit_cost", "NUMERIC(12, 2)")
    connection.exec_driver_sql(
        """
        UPDATE sale_items
           SET unit_cost = (
                SELECT ROUND(SUM(pi.line_total) * 1.0 / SUM(pi.quantity), 2)
                  FROM purchase_items pi
                  JOIN purchases p ON p.id = pi.purchase_id
                 WHERE pi.inventory_item_id = sale_items.inventory_item_id
                   AND pi.item_type = sale_items.item_type
                   AND pi.quantity > 0
                   AND p.created_at <= (
                        SELECT s.created_at FROM sales s WHERE s.id = sale_items.sale_id
                   )
           )
         WHERE unit_cost IS NULL
        """
    )


def _add_document_returns(connection: Connection) -> None:
    """Documents record what came back off them, and what was refunded.

    Both figures are stored on the document rather than summed from the
    return rows, because `balance_amount` is read by every list, ageing
    report and payment screen and none of them load returns. Existing rows
    take zero, which is what they meant before the columns existed.

    The `sale_returns` and `purchase_returns` tables themselves need no
    DDL here — `create_all` builds tables that are missing, and these are
    new in their entirety.

    TRANSFER left the movement enum in the same build. No row should hold
    it (the type was never recorded by any screen), but one that did would
    raise the moment `MovementType` parsed it, so it is rewritten to the
    correction it always effectively was.

    Safe to rerun: `_add_column` is guarded and the UPDATE matches nothing
    the second time.
    """
    for table in ("sales", "purchases"):
        _add_column(connection, table, "returned_amount", "NUMERIC(12, 2) NOT NULL DEFAULT 0")
        _add_column(connection, table, "refunded_amount", "NUMERIC(12, 2) NOT NULL DEFAULT 0")

    connection.exec_driver_sql(
        "UPDATE inventory_movements "
        "   SET movement_type = 'ADJUSTMENT', "
        "       reason = COALESCE(reason, 'Recorded before transfers were removed') "
        " WHERE movement_type = 'TRANSFER'"
    )


class _ReturnTables(NamedTuple):
    """A kind of return, and every name that differs between the two."""

    header: str
    lines: str
    header_column: str
    """What a line calls the return it belongs to."""
    line_column: str
    """What a line calls the document line it reverses."""
    document_column: str
    """What a return calls the document it is against."""
    document_lines: str
    """The table holding that document's own lines."""
    movement_kind: str
    """What a return of this kind calls itself on the stock movement it
    writes — the only other record of what came back."""


_RETURN_TABLES: tuple[_ReturnTables, ...] = (
    _ReturnTables(
        "sale_returns", "sale_return_items", "sale_return_id",
        "sale_item_id", "sale_id", "sale_items", "SALE_RETURN",
    ),
    _ReturnTables(
        "purchase_returns", "purchase_return_items", "purchase_return_id",
        "purchase_item_id", "purchase_id", "purchase_items", "PURCHASE_RETURN",
    ),
)

_RETURN_HEADER_COLUMNS: tuple[str, ...] = (
    "id", "return_no", "refund_amount", "refund_method_id", "reason", "note",
    "returned_at", "created_by_user_id", "updated_by_user_id", "created_at",
    "updated_at",
)
"""What is still a return's own once its goods have moved to its lines.
The document column differs by kind and is added to this."""

_LIFTED_LINE = (
    "item_type, inventory_item_id, quantity, unit_price, created_at, updated_at"
)
"""What a return said about its goods before it had lines to say it."""


def _lift_return_lines(connection: Connection) -> None:
    """A return became a document with lines of its own.

    It was written one row per returned line, because a return could only
    be recorded one line at a time. A customer hands back two things in
    one act — one number, one conversation about the refund — so it is
    now a header with lines, exactly like the sale it reverses.

    Rows already recorded are carried across rather than dropped: each
    becomes a return with a single line, which is what it always was.

    The order is the whole of this. The line table `create_all` has just
    built is dropped before the header is rebuilt and created again
    after, because a rebuild renames the header aside — and with foreign
    keys enforced SQLite repoints everything that references it at the
    renamed copy, which is then dropped and takes those lines with it.

    Safe to rerun: a database whose lines have already moved no longer
    has the column this reads, and is skipped.
    """
    from app.infrastructure.db.base import Base

    for returns in _RETURN_TABLES:
        if returns.line_column not in _table_columns(connection, returns.header):
            continue

        logger.info("Lifting %s lines into %s", returns.header, returns.lines)
        lifted = connection.exec_driver_sql(
            f"SELECT id, {returns.line_column}, {_LIFTED_LINE} FROM {returns.header}"
        ).fetchall()

        connection.exec_driver_sql(f"DROP TABLE {returns.lines}")
        _rebuild_to_match_model(
            connection,
            returns.header,
            (returns.document_column, *_RETURN_HEADER_COLUMNS),
        )
        Base.metadata.tables[returns.lines].create(bind=connection)

        if lifted:
            connection.exec_driver_sql(
                f"INSERT INTO {returns.lines} "
                f"       ({returns.header_column}, {returns.line_column}, "
                f"        {_LIFTED_LINE}) "
                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [tuple(row) for row in lifted],
            )


def _repair_lifted_return_lines(connection: Connection) -> None:
    """Put back return lines an earlier build of the step above lost.

    That build rebuilt the return table while the new line table already
    pointed at it. With foreign keys enforced — which is how this
    application opens a database — SQLite follows a renamed table, so the
    line table came to reference the copy being rebuilt from; dropping
    that copy cascaded the lines away with it and left the reference
    naming a table that is no longer there.

    Both are put right here. The line table is recreated so its foreign
    key names the table that is actually there, and its rows are read
    back off the stock movement each return wrote: that movement carries
    the item, the quantity and the price, which is all a line is. The
    document line it reverses is the one that traded that item on that
    document.

    A database that never ran the faulty build has nothing naming a
    missing table, and is left alone.
    """
    from app.infrastructure.db.base import Base

    for returns in _RETURN_TABLES:
        if not _references_a_missing_table(connection, returns.lines):
            continue

        logger.info("Repairing %s", returns.lines)
        connection.exec_driver_sql(f"DROP TABLE {returns.lines}")
        Base.metadata.tables[returns.lines].create(bind=connection)
        connection.exec_driver_sql(
            f"INSERT INTO {returns.lines} "
            f"       ({returns.header_column}, {returns.line_column}, item_type, "
            f"        inventory_item_id, quantity, unit_price, created_at) "
            f"SELECT m.source_document_id, line.id, m.item_type, "
            f"       m.inventory_item_id, m.quantity, m.unit_price, m.created_at "
            f"  FROM inventory_movements m "
            f"  JOIN {returns.header} r ON r.id = m.source_document_id "
            f"  JOIN {returns.document_lines} line "
            f"    ON line.id = (SELECT MIN(other.id) FROM {returns.document_lines} other "
            f"                   WHERE other.{returns.document_column} "
            f"                         = r.{returns.document_column} "
            f"                     AND other.inventory_item_id = m.inventory_item_id) "
            f" WHERE m.source_document_type = '{returns.movement_kind}'"
        )


def _add_catalogue_grouping(connection: Connection) -> None:
    """The catalogue gains a shape: categories, products, and SKUs under
    them.

    What was one flat list of items becomes a shelf (`categories`), the
    thing the shop trades in (`products`), and the stockable record under
    it — which is the item table itself, untouched. Every id, every
    foreign key and every document that names one stays exactly as it is;
    what is added is a `product_id` above them.

    Each existing item gets a product of its own name, because that is
    what it has always been: one thing, counted one way. A shop that later
    wants two variants of one product adds the second SKU itself.

    Items sharing a name become SKUs of one product rather than two
    products with the same name — the same rule the application enforces
    on the way in.

    Safe to rerun, and safe on a database that already has some of this:
    tables are created only if missing, columns added only if absent, and
    only items with no product yet are given one.
    """
    _create_if_missing(connection, "categories")
    _create_if_missing(connection, "products")
    _add_index(connection, "categories", "name")
    _add_index(connection, "products", "name")
    _add_index(connection, "products", "category_id")

    _add_column(connection, "inventory_items", "product_id", "INTEGER REFERENCES products(id)")
    _add_index(connection, "inventory_items", "product_id")

    general = _default_category_id(connection)

    # A product filed nowhere would fall out of the catalogue screen
    # entirely, so anything without a shelf goes on the default one.
    connection.exec_driver_sql(
        "UPDATE products SET category_id = ? WHERE category_id IS NULL", (general,)
    )

    connection.exec_driver_sql(
        """
        INSERT INTO products (name, category_id, created_by_user_id, created_at)
        SELECT i.name, ?, MIN(i.created_by_user_id), MIN(i.created_at)
          FROM inventory_items i
         WHERE i.product_id IS NULL
           AND NOT EXISTS (SELECT 1 FROM products p WHERE p.name = i.name)
         GROUP BY i.name
        """,
        (general,),
    )
    connection.exec_driver_sql(
        """
        UPDATE inventory_items
           SET product_id = (SELECT p.id FROM products p WHERE p.name = inventory_items.name)
         WHERE product_id IS NULL
        """
    )


def _default_category_id(connection: Connection) -> int:
    """The `General` category, made if this database has never had one.

    Matched on the name rather than on an id, because the row is written
    here on a database that already has data and by the initializer on a
    fresh one: its id differs between installations, its name never does.
    Matched case-insensitively so a shop that made its own "general"
    keeps it rather than getting a second one beside it.
    """
    from app.domain.entities.category import DEFAULT_CATEGORY_NAME

    row = connection.exec_driver_sql(
        "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (DEFAULT_CATEGORY_NAME,)
    ).fetchone()
    if row is not None:
        return int(row[0])

    connection.exec_driver_sql(
        "INSERT INTO categories (name, description, created_at) "
        "VALUES (?, 'Everything not filed anywhere else yet.', CURRENT_TIMESTAMP)",
        (DEFAULT_CATEGORY_NAME,),
    )
    return int(connection.exec_driver_sql("SELECT last_insert_rowid()").scalar_one())


def _add_transaction_units(connection: Connection) -> None:
    """A SKU can be traded in more than one unit, and a line records which.

    A shop that buys A4 by the box and sells it by the piece could not say
    so: stock was counted in whole units of whatever word was on the item,
    and half a sheet could not be sold at all. `sku_units` holds the
    alternates — "a Box is 288 Pieces" — and every document line gains the
    unit it was entered in and what that came to in base units.

    **Every existing line was entered in its item's own unit**, which is
    what `uom_id IS NULL` means, so `base_quantity` is its quantity and
    nothing that was ever traded changes value, count or cost. That is the
    whole of the backfill, and it is why the step can be rerun: it only
    fills rows that have not been filled.

    The quantity columns keep their declared `INTEGER` here while the
    models say `NUMERIC(14, 4)`. Nothing is rebuilt to close that gap on
    purpose: SQLite's declared types are affinity rather than constraint,
    an INTEGER-affinity column stores 0.5 as REAL and returns it
    unchanged, and rebuilding six tables that point at each other with
    foreign keys enforced is a real risk taken for a cosmetic difference.
    """
    _create_if_missing(connection, "sku_units")
    _add_index(connection, "sku_units", "sku_id")

    for table in ("sale_items", "purchase_items", "inventory_movements"):
        _add_column(connection, table, "base_quantity", "NUMERIC(14, 4) NOT NULL DEFAULT 0")
        _add_column(connection, table, "uom_id", "INTEGER REFERENCES sku_units(id)")
        _add_index(connection, table, "uom_id")

    # Return lines carry no unit of their own: a return is measured the
    # way the line it reverses was, and its base quantity is that line's
    # conversion applied to what came back.
    for table in ("sale_return_items", "purchase_return_items"):
        _add_column(connection, table, "base_quantity", "NUMERIC(14, 4) NOT NULL DEFAULT 0")

    for table in (
        "sale_items",
        "purchase_items",
        "inventory_movements",
        "sale_return_items",
        "purchase_return_items",
    ):
        connection.exec_driver_sql(
            f"UPDATE {table} SET base_quantity = quantity "
            f" WHERE base_quantity IS NULL OR base_quantity = 0"
        )


def _references_a_missing_table(connection: Connection, table: str) -> bool:
    """Whether any of this table's foreign keys names a table that is
    not there — which is what a rebuild leaves behind when foreign keys
    are enforced while something still points at what it rebuilt."""
    return any(
        not _table_exists(connection, row[2])
        for row in connection.exec_driver_sql(f"PRAGMA foreign_key_list({table})")
    )


_STEPS: tuple[Callable[[Connection], None], ...] = (
    _drop_catalogue_prices,
    _relax_payment_method_links,
    _fold_cards_into_inventory,
    _add_party_opening_balance,
    _add_sale_line_cost,
    _add_document_returns,
    _lift_return_lines,
    _repair_lifted_return_lines,
    _add_catalogue_grouping,
    _add_transaction_units,
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


def stamp_current_version(engine: Engine) -> None:
    """Record a database that has just been created as already up to date.

    `create_all` builds every table in its present shape, so a database
    made a moment ago has, by definition, been through every step in
    `_STEPS` — there is no legacy column to drop and no historical row to
    fill in. Left unstamped it reports version 0, which sends `migrate`
    through all of them and, worse, takes a `.v0.backup` copy of a file
    holding nothing: a fresh installation would be born with a useless
    duplicate of an empty database beside it.

    Only ever called for a database with no tables in it. Stamping one
    that has data would skip the steps it genuinely needs.
    """
    with engine.begin() as connection:
        # Not parameterisable — PRAGMA takes a literal. The value is the
        # length of a tuple defined above, never external input.
        connection.exec_driver_sql(f"PRAGMA user_version = {len(_STEPS)}")


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
