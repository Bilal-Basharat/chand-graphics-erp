"""
The two steps that gave the catalogue a shape and its items units.

Both run on databases that are not empty and, on the developer's own
machine, on one that already has some of what they add. So what is
checked here is not only that they do their work, but that they do it to
a database part-way through it, do it once, and change nothing that was
ever traded.

The old shape is made by taking the new one away — the same trick
`test_upgrade.py` uses for the cost backfill: build the data with the
live use cases, strip the columns, migrate, and compare against what the
application itself wrote.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import event, text

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    PurchaseItemCommand,
    SaleItemCommand,
)
from app.application.use_cases.inventory_items import CreateInventoryItemUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.application.use_cases.sales import CreateSaleUseCase
from app.domain.entities.category import DEFAULT_CATEGORY_NAME
from app.domain.enums.item_type import ItemType
from app.infrastructure.db import upgrade

_BEFORE_CATALOGUE = 8
"""Where a database sits just before the catalogue step."""

_LINE_TABLES = (
    "sale_items",
    "purchase_items",
    "inventory_movements",
    "sale_return_items",
    "purchase_return_items",
)


@pytest.fixture()
def no_backup(monkeypatch):
    """`_backup` copies the module-level DATABASE_PATH — the developer's
    own database, not this test's. Never let it run here."""
    monkeypatch.setattr(upgrade, "_backup", lambda version: None)


def _turn_foreign_keys_on(dbapi_connection, _record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def _enforcing(engine) -> None:
    """Open the database the way the application does — see
    `app/infrastructure/db/database.py`."""
    event.listen(engine, "connect", _turn_foreign_keys_on)
    engine.dispose()


def _trading(uow, admin_session):
    """A shop's worth of history, written by the live use cases."""
    paper = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="A4 Ivory", unit="sheets")
    )
    ink = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Black Ink", unit="tins")
    )
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-1",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=paper.id,
                    quantity=Decimal("500"),
                    unit_price=Decimal("10.00"),
                ),
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=ink.id,
                    quantity=Decimal("4"),
                    unit_price=Decimal("900.00"),
                ),
            ],
            payments=[],
        )
    )
    CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-1",
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=paper.id,
                    quantity=Decimal("120"),
                    unit_price=Decimal("18.00"),
                )
            ],
            payments=[],
        )
    )
    return paper, ink


_OLD_SHAPE: dict[str, tuple[str, tuple[str, ...]]] = {
    "inventory_items": (
        """
        CREATE TABLE inventory_items (
            id INTEGER NOT NULL,
            name VARCHAR(150) NOT NULL,
            current_stock INTEGER NOT NULL,
            minimum_stock INTEGER NOT NULL,
            description VARCHAR(500),
            unit VARCHAR(20),
            cabinet_id INTEGER,
            created_by_user_id INTEGER,
            updated_by_user_id INTEGER,
            created_at DATETIME NOT NULL,
            updated_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(cabinet_id) REFERENCES cabinets (id),
            FOREIGN KEY(created_by_user_id) REFERENCES users (id),
            FOREIGN KEY(updated_by_user_id) REFERENCES users (id)
        )
        """,
        (
            "id", "name", "current_stock", "minimum_stock", "description", "unit",
            "cabinet_id", "created_by_user_id", "updated_by_user_id", "created_at",
            "updated_at",
        ),
    ),
    "sale_items": (
        """
        CREATE TABLE sale_items (
            id INTEGER NOT NULL,
            sale_id INTEGER NOT NULL,
            item_type VARCHAR(14) NOT NULL,
            inventory_item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price NUMERIC(12, 2) NOT NULL,
            discount_amount NUMERIC(12, 2) NOT NULL,
            unit_cost NUMERIC(12, 2),
            line_total NUMERIC(12, 2) NOT NULL,
            previous_stock INTEGER,
            resulting_stock INTEGER,
            note VARCHAR(500),
            created_at DATETIME NOT NULL,
            updated_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(sale_id) REFERENCES sales (id) ON DELETE CASCADE,
            FOREIGN KEY(inventory_item_id) REFERENCES inventory_items (id)
        )
        """,
        (
            "id", "sale_id", "item_type", "inventory_item_id", "quantity", "unit_price",
            "discount_amount", "unit_cost", "line_total", "previous_stock",
            "resulting_stock", "note", "created_at", "updated_at",
        ),
    ),
    "purchase_items": (
        """
        CREATE TABLE purchase_items (
            id INTEGER NOT NULL,
            purchase_id INTEGER NOT NULL,
            item_type VARCHAR(14) NOT NULL,
            inventory_item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price NUMERIC(12, 2) NOT NULL,
            discount_amount NUMERIC(12, 2) NOT NULL,
            line_total NUMERIC(12, 2) NOT NULL,
            previous_stock INTEGER,
            resulting_stock INTEGER,
            note VARCHAR(500),
            created_at DATETIME NOT NULL,
            updated_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(purchase_id) REFERENCES purchases (id) ON DELETE CASCADE,
            FOREIGN KEY(inventory_item_id) REFERENCES inventory_items (id)
        )
        """,
        (
            "id", "purchase_id", "item_type", "inventory_item_id", "quantity", "unit_price",
            "discount_amount", "line_total", "previous_stock", "resulting_stock", "note",
            "created_at", "updated_at",
        ),
    ),
    "inventory_movements": (
        """
        CREATE TABLE inventory_movements (
            id INTEGER NOT NULL,
            movement_type VARCHAR(10) NOT NULL,
            item_type VARCHAR(14) NOT NULL,
            source_document_type VARCHAR(30),
            source_document_id INTEGER,
            quantity INTEGER NOT NULL,
            unit_price NUMERIC(12, 2),
            previous_stock INTEGER,
            resulting_stock INTEGER,
            reference_no VARCHAR(100),
            reason VARCHAR(255),
            note VARCHAR(500),
            occurred_at DATETIME NOT NULL,
            inventory_item_id INTEGER NOT NULL,
            created_by_user_id INTEGER,
            updated_by_user_id INTEGER,
            created_at DATETIME NOT NULL,
            updated_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(inventory_item_id) REFERENCES inventory_items (id),
            FOREIGN KEY(created_by_user_id) REFERENCES users (id),
            FOREIGN KEY(updated_by_user_id) REFERENCES users (id)
        )
        """,
        (
            "id", "movement_type", "item_type", "source_document_type", "source_document_id",
            "quantity", "unit_price", "previous_stock", "resulting_stock", "reference_no",
            "reason", "note", "occurred_at", "inventory_item_id", "created_by_user_id",
            "updated_by_user_id", "created_at", "updated_at",
        ),
    ),
}
"""The four tables as a shop in the field still has them, written out.

Not produced by dropping columns from the current ones: SQLite refuses to
drop a column a table-level foreign key names, which `product_id` and
`uom_id` both are. Written out rather than generated, so what these tests
migrate is a schema somebody can read and compare against a customer's
file rather than one the test derived and might have derived wrongly.
"""


def _to_the_old_shape(engine) -> None:
    """Put the database back to how one written before these steps looks.

    The rows are carried across unchanged — same ids, same values — so
    what the steps run against is the history the use cases just wrote.
    """
    with engine.begin() as connection:
        for table in ("sale_return_items", "purchase_return_items"):
            connection.exec_driver_sql(f"ALTER TABLE {table} DROP COLUMN base_quantity")

        for table, (ddl, columns) in _OLD_SHAPE.items():
            carried = ", ".join(columns)
            connection.exec_driver_sql(f"ALTER TABLE {table} RENAME TO {table}_new")
            connection.exec_driver_sql(ddl)
            connection.exec_driver_sql(
                f"INSERT INTO {table} ({carried}) SELECT {carried} FROM {table}_new"
            )
            connection.exec_driver_sql(f"DROP TABLE {table}_new")

        connection.exec_driver_sql("DROP TABLE sku_units")
        connection.exec_driver_sql("DROP TABLE products")
        connection.exec_driver_sql("DROP TABLE categories")
        connection.exec_driver_sql(f"PRAGMA user_version = {_BEFORE_CATALOGUE}")


def _rows(engine, statement: str) -> list[tuple]:
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text(statement))]


def _quantities(engine) -> dict[str, list[tuple]]:
    return {
        table: _rows(engine, f"SELECT id, quantity FROM {table} ORDER BY id")
        for table in _LINE_TABLES
    }


# ------------------------------------------------------------- the catalogue


def test_every_item_comes_out_with_a_product_of_its_own(
    uow, admin_session, db_engine, no_backup
):
    _trading(uow, admin_session)
    _to_the_old_shape(db_engine)

    upgrade.migrate(db_engine)

    assert _rows(
        db_engine,
        "SELECT i.name, p.name FROM inventory_items i "
        "JOIN products p ON p.id = i.product_id ORDER BY i.id",
    ) == [("A4 Ivory", "A4 Ivory"), ("Black Ink", "Black Ink")]


def test_those_products_land_on_the_default_shelf(uow, admin_session, db_engine, no_backup):
    _trading(uow, admin_session)
    _to_the_old_shape(db_engine)

    upgrade.migrate(db_engine)

    assert _rows(
        db_engine,
        "SELECT DISTINCT c.name FROM products p JOIN categories c ON c.id = p.category_id",
    ) == [(DEFAULT_CATEGORY_NAME,)]


def test_two_items_of_one_name_become_two_versions_of_one_product(
    uow, admin_session, db_engine, no_backup
):
    """What the application enforces on the way in, applied to what is
    already there: one name is one product."""
    _trading(uow, admin_session)
    _to_the_old_shape(db_engine)
    with db_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO inventory_items (name, current_stock, minimum_stock, created_at) "
            "VALUES ('A4 Ivory', 0, 0, CURRENT_TIMESTAMP)"
        )

    upgrade.migrate(db_engine)

    assert _rows(db_engine, "SELECT COUNT(*) FROM products")[0][0] == 2
    assert _rows(
        db_engine,
        "SELECT COUNT(*) FROM inventory_items i "
        "JOIN products p ON p.id = i.product_id WHERE p.name = 'A4 Ivory'",
    )[0][0] == 2


# ------------------------------------------------------------------ the units


def test_every_line_reads_as_having_been_entered_in_its_item_s_own_unit(
    uow, admin_session, db_engine, no_backup
):
    _trading(uow, admin_session)
    before = _quantities(db_engine)
    _to_the_old_shape(db_engine)

    upgrade.migrate(db_engine)

    for table in _LINE_TABLES:
        assert _rows(db_engine, f"SELECT id, base_quantity FROM {table} ORDER BY id") == [
            (line_id, quantity) for line_id, quantity in before[table]
        ]
    assert _rows(db_engine, "SELECT COUNT(*) FROM sale_items WHERE uom_id IS NOT NULL") == [(0,)]


def test_nothing_that_was_traded_changes(uow, admin_session, db_engine, no_backup):
    _trading(uow, admin_session)
    before = {
        "quantities": _quantities(db_engine),
        "stock": _rows(db_engine, "SELECT id, current_stock FROM inventory_items ORDER BY id"),
        "lines": _rows(db_engine, "SELECT id, line_total, unit_cost FROM sale_items ORDER BY id"),
        "sales": _rows(db_engine, "SELECT id, grand_total FROM sales ORDER BY id"),
    }
    _to_the_old_shape(db_engine)

    upgrade.migrate(db_engine)

    assert _quantities(db_engine) == before["quantities"]
    assert _rows(db_engine, "SELECT id, current_stock FROM inventory_items ORDER BY id") == (
        before["stock"]
    )
    assert _rows(db_engine, "SELECT id, line_total, unit_cost FROM sale_items ORDER BY id") == (
        before["lines"]
    )
    assert _rows(db_engine, "SELECT id, grand_total FROM sales ORDER BY id") == before["sales"]


# ------------------------------------------------------------ running it again


def test_running_the_steps_twice_changes_nothing(uow, admin_session, db_engine, no_backup):
    _trading(uow, admin_session)
    _to_the_old_shape(db_engine)
    upgrade.migrate(db_engine)
    after_once = {
        "products": _rows(db_engine, "SELECT id, name, category_id FROM products ORDER BY id"),
        "items": _rows(db_engine, "SELECT id, product_id FROM inventory_items ORDER BY id"),
        "quantities": _quantities(db_engine),
    }

    with db_engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version = {_BEFORE_CATALOGUE}")
    upgrade.migrate(db_engine)

    assert _rows(db_engine, "SELECT id, name, category_id FROM products ORDER BY id") == (
        after_once["products"]
    )
    assert _rows(db_engine, "SELECT id, product_id FROM inventory_items ORDER BY id") == (
        after_once["items"]
    )
    assert _quantities(db_engine) == after_once["quantities"]


def test_a_database_part_way_through_converges_rather_than_failing(
    uow, admin_session, db_engine, no_backup
):
    """The state this developer's own database was found in: the tables of
    an abandoned attempt at this feature, and none of its columns."""
    _trading(uow, admin_session)
    _to_the_old_shape(db_engine)
    with db_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE categories (id INTEGER PRIMARY KEY, name VARCHAR(150) NOT NULL, "
            "description VARCHAR(500), created_by_user_id INTEGER, "
            "updated_by_user_id INTEGER, created_at DATETIME NOT NULL, updated_at DATETIME)"
        )
        connection.exec_driver_sql(
            "INSERT INTO categories (name, created_at) VALUES ('Papers', CURRENT_TIMESTAMP)"
        )

    upgrade.migrate(db_engine)

    names = {name for (name,) in _rows(db_engine, "SELECT name FROM categories")}
    assert names == {"Papers", DEFAULT_CATEGORY_NAME}
    assert _rows(db_engine, "SELECT COUNT(*) FROM inventory_items WHERE product_id IS NULL") == [
        (0,)
    ]


def test_the_steps_run_with_foreign_keys_enforced(uow, admin_session, db_engine, no_backup):
    """How the application actually opens the database."""
    _trading(uow, admin_session)
    _to_the_old_shape(db_engine)
    _enforcing(db_engine)

    upgrade.migrate(db_engine)

    with db_engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    assert _rows(db_engine, "SELECT COUNT(*) FROM inventory_items WHERE product_id IS NULL") == [
        (0,)
    ]
