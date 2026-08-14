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
from sqlalchemy import text

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    InventoryMovementCommand,
    PurchaseItemCommand,
    SaleItemCommand,
)
from app.application.use_cases.inventory_items import CreateInventoryItemUseCase
from app.application.use_cases.inventory_movements import RecordInventoryMovementUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase
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
