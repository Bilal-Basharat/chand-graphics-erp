"""
The cost backfill, checked against the thing it is meant to reproduce.

A migration that fills a column has one job: put in what the live code
would have put in. So the test records what `CreateSaleUseCase` wrote,
takes it away, migrates, and compares — rather than asserting a number
worked out by hand, which would only prove the test and the migration
made the same mistake.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, text

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    InventoryMovementCommand,
    PurchaseItemCommand,
    RecordSaleReturnCommand,
    ReturnedLineCommand,
    SaleItemCommand,
)
from app.application.use_cases.inventory_items import CreateInventoryItemUseCase
from app.application.use_cases.inventory_movements import RecordInventoryMovementUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.application.use_cases.returns import RecordSaleReturnUseCase
from app.application.use_cases.sales import CreateSaleUseCase
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.infrastructure.db import upgrade

_VERSION_BEFORE = 4
"""Where a database sits just before the sale-line cost step."""


@pytest.fixture()
def no_backup(monkeypatch):
    """`_backup` copies the module-level DATABASE_PATH — the developer's
    own database, not this test's. Never let it run here."""
    monkeypatch.setattr(upgrade, "_backup", lambda version: None)


@pytest.fixture()
def recorded_backups(monkeypatch) -> list[int]:
    """Which versions `migrate` decided were worth copying the file for."""
    taken: list[int] = []
    monkeypatch.setattr(upgrade, "_backup", taken.append)
    return taken


def _costs_by_invoice(engine) -> dict[str, list]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT s.invoice_no, i.id, i.unit_cost FROM sale_items i "
                "JOIN sales s ON s.id = i.sale_id ORDER BY i.id"
            )
        )
        costs: dict[str, list] = {}
        for invoice_no, _line_id, unit_cost in rows:
            costs.setdefault(invoice_no, []).append(unit_cost)
        return costs


def _trading(uow, admin_session):
    """Two items: one bought twice at different prices, one never bought."""
    bought = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Art Card", unit="sheets")
    )
    counted_in = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Gold Foil", unit="rolls")
    )
    RecordInventoryMovementUseCase(uow, admin_session).execute(
        InventoryMovementCommand(
            movement_type=MovementType.ADJUSTMENT,
            item_type=ItemType.INVENTORY_ITEM,
            inventory_item_id=counted_in.id,
            quantity_change=50,
            reason="Opening stock count",
        )
    )

    for number, price in (("PUR-1", "10.00"), ("PUR-2", "20.00")):
        CreatePurchaseUseCase(uow, admin_session).execute(
            CreatePurchaseCommand(
                purchase_no=number,
                items=[
                    PurchaseItemCommand(
                        item_type=ItemType.INVENTORY_ITEM,
                        inventory_item_id=bought.id,
                        quantity=100,
                        unit_price=Decimal(price),
                    )
                ],
            )
        )

    for number, item in (("INV-1", bought), ("INV-2", counted_in)):
        CreateSaleUseCase(uow, admin_session).execute(
            CreateSaleCommand(
                invoice_no=number,
                items=[
                    SaleItemCommand(
                        item_type=ItemType.INVENTORY_ITEM,
                        inventory_item_id=item.id,
                        quantity=5,
                        unit_price=Decimal("40.00"),
                    )
                ],
            )
        )


_RETURNS_BEFORE = 6
"""Where a database sits just before returns gained lines of their own."""

_RETURNS_LOST = 7
"""Where the build that lost those lines left a database."""

_WHEN = "2026-01-01 00:00:00"

_FLAT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("sale_item_id", "INTEGER"),
    ("item_type", "VARCHAR(30)"),
    ("inventory_item_id", "INTEGER"),
    ("quantity", "INTEGER"),
    ("unit_price", "NUMERIC(12, 2)"),
)
"""What a return carried on itself before its goods moved to its lines."""


def _a_flat_return(engine, sale_id: int, line_id: int, item_id: int) -> None:
    """Write the return a database built before this step would hold: the
    goods on the return row itself, one row per line that came back."""
    with engine.begin() as connection:
        for column, definition in _FLAT_COLUMNS:
            connection.exec_driver_sql(
                f"ALTER TABLE sale_returns ADD COLUMN {column} {definition}"
            )
        connection.exec_driver_sql(
            "INSERT INTO sale_returns (return_no, sale_id, sale_item_id, item_type, "
            "                          inventory_item_id, quantity, unit_price, "
            "                          refund_amount, returned_at, created_at) "
            "VALUES ('SR-1', ?, ?, 'INVENTORY_ITEM', ?, 4, 20.00, 80.00, ?, ?)",
            # As text, the way the driver stores a datetime — and
            # without the adapter deprecation a datetime object draws.
            (sale_id, line_id, item_id, _WHEN, _WHEN),
        )
        connection.exec_driver_sql(f"PRAGMA user_version = {_RETURNS_BEFORE}")


def _turn_foreign_keys_on(dbapi_connection, _record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def _enforcing(engine) -> None:
    """Open the database the way the application does — see
    `app/infrastructure/db/database.py`.

    The bare test engine leaves foreign keys off, and with them off
    SQLite neither follows a renamed table nor cascades a delete. That is
    the difference a migration which rebuilt a table something already
    pointed at got through on.
    """
    event.listen(engine, "connect", _turn_foreign_keys_on)
    # So the connections already pooled are made again with them on.
    engine.dispose()


def _forget_the_costs(engine) -> None:
    """Put the database back to how one written before this step looks."""
    with engine.begin() as connection:
        connection.execute(text("UPDATE sale_items SET unit_cost = NULL"))
        connection.exec_driver_sql(f"PRAGMA user_version = {_VERSION_BEFORE}")


def test_a_brand_new_database_is_not_backed_up_before_it_holds_anything(
    db_engine, recorded_backups
):
    """`db_engine` is a database `create_all` has just built, which is
    what a first run on a customer's machine has. Every step is already
    satisfied, so copying the file would leave a fresh installation with
    a duplicate of an empty database beside it."""
    upgrade.stamp_current_version(db_engine)

    upgrade.migrate(db_engine)

    assert recorded_backups == []


def test_a_brand_new_database_is_recorded_as_up_to_date(db_engine):
    upgrade.stamp_current_version(db_engine)

    with db_engine.connect() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
    assert version == len(upgrade._STEPS)


def test_a_database_with_history_is_still_backed_up(uow, admin_session, db_engine, recorded_backups):
    """The other half of the same rule: a file that has something to lose
    is copied before it is altered."""
    _trading(uow, admin_session)
    _forget_the_costs(db_engine)

    upgrade.migrate(db_engine)

    assert recorded_backups == [_VERSION_BEFORE]


def test_the_backfill_reproduces_what_a_live_sale_records(
    uow, admin_session, db_engine, no_backup
):
    _trading(uow, admin_session)
    written_live = _costs_by_invoice(db_engine)
    assert written_live["INV-1"] == [Decimal("15.00")], "the live path itself changed"

    _forget_the_costs(db_engine)
    assert _costs_by_invoice(db_engine) == {"INV-1": [None], "INV-2": [None]}

    upgrade.migrate(db_engine)

    assert _costs_by_invoice(db_engine) == written_live


def test_stock_that_was_never_bought_stays_uncosted(uow, admin_session, db_engine, no_backup):
    """NULL, not zero. Zero would report the whole line as profit."""
    _trading(uow, admin_session)
    _forget_the_costs(db_engine)

    upgrade.migrate(db_engine)

    assert _costs_by_invoice(db_engine)["INV-2"] == [None]


def test_the_step_leaves_the_version_where_the_code_is(uow, admin_session, db_engine, no_backup):
    _trading(uow, admin_session)
    _forget_the_costs(db_engine)

    upgrade.migrate(db_engine)

    with db_engine.connect() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
    assert version == len(upgrade._STEPS)


def test_migrating_twice_changes_nothing(uow, admin_session, db_engine, no_backup):
    """Every step is written to be safe to rerun, and this one guards on
    `unit_cost IS NULL` to be."""
    _trading(uow, admin_session)
    _forget_the_costs(db_engine)

    upgrade.migrate(db_engine)
    once = _costs_by_invoice(db_engine)
    upgrade.migrate(db_engine)

    assert _costs_by_invoice(db_engine) == once


def test_a_purchase_made_after_a_sale_does_not_reach_back_into_it(
    uow, admin_session, db_engine, no_backup
):
    """The backfill is bounded by each sale's own date. A lifetime average
    would price last year's invoice with this year's paper."""
    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Art Card", unit="sheets")
    )
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-1",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=100,
                    unit_price=Decimal("10.00"),
                )
            ],
        )
    )
    CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-1",
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=5,
                    unit_price=Decimal("40.00"),
                )
            ],
        )
    )
    # A later purchase at a much higher price, dated after the sale.
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-2",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=100,
                    unit_price=Decimal("90.00"),
                )
            ],
        )
    )
    later = datetime.now() + timedelta(days=1)
    with db_engine.begin() as connection:
        connection.execute(
            text("UPDATE purchases SET created_at = :when WHERE purchase_no = 'PUR-2'"),
            {"when": later},
        )

    _forget_the_costs(db_engine)
    upgrade.migrate(db_engine)

    assert _costs_by_invoice(db_engine)["INV-1"] == [Decimal("10.00")]


def test_a_return_recorded_before_it_had_lines_keeps_its_goods(
    uow, admin_session, db_engine, no_backup
):
    """The step moves a return's goods onto a line of its own.

    Read back through the code that reads returns today, not by counting
    columns: what matters is that a return recorded last week is still
    worth what it was worth, and still says what came back.
    """
    _trading(uow, admin_session)
    with uow as u:
        sale = u.sales.get_by_invoice_no("INV-1")
    line = sale.items[0]
    _a_flat_return(db_engine, sale.id, line.id, line.inventory_item_id)

    upgrade.migrate(db_engine)

    with uow as u:
        returns = u.sale_returns.list_by_sale_id(sale.id)

    assert len(returns) == 1
    recorded = returns[0]
    assert recorded.return_no == "SR-1"
    assert recorded.refund_amount == Decimal("80.00")
    assert [(item.sale_item_id, item.quantity, item.unit_price) for item in recorded.items] == [
        (line.id, 4, Decimal("20.00"))
    ]
    assert recorded.return_amount == Decimal("80.00")


def test_lifting_a_return_s_lines_twice_changes_nothing(
    uow, admin_session, db_engine, no_backup
):
    """A database half-way through an upgrade converges rather than
    doubling the lines it already moved."""
    _trading(uow, admin_session)
    with uow as u:
        sale = u.sales.get_by_invoice_no("INV-1")
    _a_flat_return(db_engine, sale.id, sale.items[0].id, sale.items[0].inventory_item_id)

    upgrade.migrate(db_engine)
    with db_engine.begin() as connection:
        connection.exec_driver_sql(f"PRAGMA user_version = {_RETURNS_BEFORE}")
    upgrade.migrate(db_engine)

    with uow as u:
        returns = u.sale_returns.list_by_sale_id(sale.id)
    assert len(returns[0].items) == 1


def test_the_lifted_lines_survive_foreign_keys_being_enforced(
    uow, admin_session, db_engine, no_backup
):
    """The line table must end up pointing at the return table itself.

    Pointed at the copy a rebuild works from, it is emptied by cascade
    the moment that copy is dropped — which is what took the goods off
    every return already recorded.
    """
    _trading(uow, admin_session)
    with uow as u:
        sale = u.sales.get_by_invoice_no("INV-1")
    line = sale.items[0]
    _a_flat_return(db_engine, sale.id, line.id, line.inventory_item_id)
    _enforcing(db_engine)

    upgrade.migrate(db_engine)

    with db_engine.connect() as connection:
        referenced = [
            row[2]
            for row in connection.exec_driver_sql(
                "PRAGMA foreign_key_list(sale_return_items)"
            )
        ]
        lifted = connection.exec_driver_sql(
            "SELECT sale_item_id, quantity, unit_price FROM sale_return_items"
        ).fetchall()

    assert "sale_returns" in referenced
    assert "sale_returns_old" not in referenced
    assert [tuple(row) for row in lifted] == [(line.id, 4, Decimal("20.00"))]


def _lose_the_lines(engine, returns) -> None:
    """Do what the faulty build did: rebuild the return table while the
    line table already points at it, with foreign keys enforced."""
    with engine.begin() as connection:
        upgrade._rebuild_to_match_model(
            connection,
            returns.header,
            (returns.document_column, *upgrade._RETURN_HEADER_COLUMNS),
        )
        connection.exec_driver_sql(f"PRAGMA user_version = {_RETURNS_LOST}")


def test_lines_lost_by_the_faulty_rebuild_are_read_back_off_the_movements(
    uow, admin_session, db_engine, no_backup
):
    """A return keeps the stock movement it wrote, and that movement
    carries the item, the quantity and the price — which is all a line
    is. So the goods can be put back on returns that lost them."""
    _trading(uow, admin_session)
    with uow as u:
        sale = u.sales.get_by_invoice_no("INV-1")
    line = sale.items[0]
    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=line.id, quantity=2)],
        )
    )
    _enforcing(db_engine)
    _lose_the_lines(db_engine, upgrade._RETURN_TABLES[0])

    with uow as u:
        assert u.sale_returns.returned_quantity_for_line(line.id) == 0  # they are gone

    upgrade.migrate(db_engine)

    with uow as u:
        recorded = u.sale_returns.list_by_sale_id(sale.id)
    assert [(item.sale_item_id, item.quantity, item.unit_price) for item in recorded[0].items] == [
        (line.id, 2, Decimal("40.00"))
    ]
    assert recorded[0].return_amount == Decimal("80.00")


def test_a_database_that_never_lost_its_lines_is_left_alone(
    uow, admin_session, db_engine, no_backup
):
    """The repair reaches only what names a table that is not there."""
    _trading(uow, admin_session)
    with uow as u:
        sale = u.sales.get_by_invoice_no("INV-1")
    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=2)],
        )
    )
    _enforcing(db_engine)

    upgrade.migrate(db_engine)

    with uow as u:
        recorded = u.sale_returns.list_by_sale_id(sale.id)
    assert len(recorded[0].items) == 1
