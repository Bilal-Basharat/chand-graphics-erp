from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.application.auth.exceptions import AuthorizationError
from app.application.dto.commands import (
    CreateCustomerCommand,
    CreateExpenseCommand,
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    CreateSupplierCommand,
    InventoryMovementCommand,
    PurchaseItemCommand,
    RecordSalePaymentCommand,
    SaleItemCommand,
    SalePaymentCommand,
)
from app.application.dto.queries import AgeingQuery, ReportQuery
from app.application.reporting.sources import PayablesSource, ReceivablesSource
from app.application.use_cases.expenses import CreateExpenseUseCase
from app.application.use_cases.inventory_items import CreateInventoryItemUseCase
from app.application.use_cases.inventory_movements import RecordInventoryMovementUseCase
from app.application.use_cases.master_data import (
    CreateCustomerUseCase,
    CreateSupplierUseCase,
)
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.application.use_cases.reports import (
    AGE_BANDS,
    UNCATEGORISED,
    UNNAMED_ITEM,
    UNNAMED_PARTY,
    GetAgeingUseCase,
    GetItemProfitabilityUseCase,
    GetProfitAndLossUseCase,
    build_ageing,
    build_item_profitability,
    build_profit_and_loss,
)
from app.application.use_cases.sales import CreateSaleUseCase, RecordSalePaymentUseCase
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.domain.repositories.aggregates import (
    CategorySpendRow,
    CostTotals,
    ItemMarginRow,
    OutstandingRow,
    RevenueTotals,
)

_ALL_TIME = datetime(1970, 1, 1)
_FAR_FUTURE = datetime(2999, 1, 1)
_NOW = datetime(2026, 8, 11)


# ---------------------------------------------------------------- profit & loss


def _revenue(net: str = "1000.00", gross: str | None = None, discounts: str = "0.00"):
    return RevenueTotals(
        gross=Decimal(gross or net),
        discounts=Decimal(discounts),
        net=Decimal(net),
        invoice_count=1,
    )


def _cost(cost: str = "600.00", uncosted_lines: int = 0, uncosted_revenue: str = "0.00"):
    return CostTotals(
        cost_of_goods_sold=Decimal(cost),
        uncosted_lines=uncosted_lines,
        uncosted_revenue=Decimal(uncosted_revenue),
    )


def _profit_and_loss(revenue=None, cost=None, spending=(), names=None, stock="0.00"):
    return build_profit_and_loss(
        _ALL_TIME,
        _NOW,
        revenue or _revenue(),
        cost or _cost(),
        spending,
        names or {},
        Decimal(stock),
    )


def test_profit_is_revenue_less_cost_less_expenses():
    report = _profit_and_loss(
        spending=[CategorySpendRow(category_id=1, count=2, total=Decimal("100.00"))],
        names={1: "Rent"},
    )

    assert report.gross_profit == Decimal("400.00")
    assert report.expenses_total == Decimal("100.00")
    assert report.net_profit == Decimal("300.00")
    assert report.gross_margin == Decimal("40.0")


def test_stock_bought_is_carried_but_never_subtracted():
    """Buying stock is money moved, not money gone — it is the whole
    difference between this and the figure it replaced."""
    report = _profit_and_loss(stock="50000.00")

    assert report.stock_bought == Decimal("50000.00")
    assert report.net_profit == Decimal("400.00")


def test_margin_of_nothing_sold_is_unknown_not_zero():
    report = _profit_and_loss(revenue=_revenue(net="0.00"), cost=_cost(cost="0.00"))

    assert report.gross_margin is None
    assert report.net_margin is None
    assert report.net_profit == Decimal("0.00")


def test_uncosted_lines_are_reported_never_folded_in_as_zero():
    report = _profit_and_loss(
        cost=_cost(cost="600.00", uncosted_lines=2, uncosted_revenue="150.00")
    )

    assert report.is_complete is False
    assert report.uncosted_lines == 2
    assert report.uncosted_revenue == Decimal("150.00")
    # The unknown cost is absent from COGS, so the profit is knowingly
    # overstated rather than silently wrong.
    assert report.cost_of_goods_sold == Decimal("600.00")


def test_spending_is_ordered_biggest_first_and_shares_reach_a_hundred():
    report = _profit_and_loss(
        spending=[
            CategorySpendRow(category_id=1, count=1, total=Decimal("25.00")),
            CategorySpendRow(category_id=2, count=3, total=Decimal("75.00")),
        ],
        names={1: "Transport", 2: "Rent"},
    )

    assert [line.name for line in report.spending] == ["Rent", "Transport"]
    assert [line.share for line in report.spending] == [Decimal("75.0"), Decimal("25.0")]
    assert sum(line.share for line in report.spending) == Decimal("100.0")
    assert report.expense_count == 4


def test_spending_with_no_category_is_named_rather_than_dropped():
    report = _profit_and_loss(
        spending=[CategorySpendRow(category_id=None, count=1, total=Decimal("10.00"))]
    )

    assert [line.name for line in report.spending] == [UNCATEGORISED]


def test_a_period_with_no_spending_divides_by_nothing():
    report = _profit_and_loss(spending=[])

    assert report.spending == ()
    assert report.expenses_total == Decimal("0.00")


# ---------------------------------------------------------------- by item


def test_an_item_never_bought_reports_no_cost_rather_than_total_margin():
    report = build_item_profitability(
        _ALL_TIME,
        _NOW,
        [ItemMarginRow(item_id=1, quantity_sold=5, revenue=Decimal("500.00"),
                       cost=Decimal("0.00"), uncosted_lines=3)],
        {1: "Gold foil"},
    )

    row = report.rows[0]
    assert row.cost is None
    assert row.profit is None
    assert row.margin is None
    # ...and the unknown is not quietly added to the period's cost.
    assert report.cost == Decimal("0.00")
    assert report.uncosted_lines == 3


def test_a_partly_costed_item_keeps_the_part_that_is_known():
    report = build_item_profitability(
        _ALL_TIME,
        _NOW,
        [ItemMarginRow(item_id=1, quantity_sold=10, revenue=Decimal("500.00"),
                       cost=Decimal("200.00"), uncosted_lines=1)],
        {1: "Art card"},
    )

    row = report.rows[0]
    assert row.cost == Decimal("200.00")
    assert row.profit == Decimal("300.00")
    assert row.uncosted_lines == 1


def test_an_item_since_deleted_is_named_rather_than_raising():
    report = build_item_profitability(
        _ALL_TIME,
        _NOW,
        [ItemMarginRow(item_id=99, quantity_sold=1, revenue=Decimal("10.00"),
                       cost=Decimal("4.00"), uncosted_lines=0)],
        {},
    )

    assert report.rows[0].name == UNNAMED_ITEM


def test_items_are_ordered_by_what_they_brought_in():
    report = build_item_profitability(
        _ALL_TIME,
        _NOW,
        [
            ItemMarginRow(item_id=1, quantity_sold=1, revenue=Decimal("10.00"),
                          cost=Decimal("5.00"), uncosted_lines=0),
            ItemMarginRow(item_id=2, quantity_sold=1, revenue=Decimal("90.00"),
                          cost=Decimal("40.00"), uncosted_lines=0),
        ],
        {1: "Small", 2: "Big"},
    )

    assert [row.name for row in report.rows] == ["Big", "Small"]
    assert report.revenue == Decimal("100.00")
    assert report.profit == Decimal("55.00")


# ---------------------------------------------------------------- ageing


def _owing(days_old: int, amount: str = "100.00", party: str | None = "Ahmad"):
    return OutstandingRow(
        reference=f"INV-{days_old}",
        party_name=party,
        occurred_at=_NOW - timedelta(days=days_old),
        outstanding=Decimal(amount),
    )


@pytest.mark.parametrize(
    ("days_old", "band"),
    [
        (0, "0-30 days"),
        (30, "0-30 days"),
        (31, "31-60 days"),
        (60, "31-60 days"),
        (61, "61-90 days"),
        (90, "61-90 days"),
        (91, "Over 90 days"),
        (900, "Over 90 days"),
    ],
)
def test_a_debt_lands_in_the_band_its_age_puts_it_in(days_old, band):
    """The boundaries are the only thing in this report that can be wrong."""
    report = build_ageing(_NOW, [_owing(days_old)])

    assert report.lines[0].band == band
    assert report.lines[0].age_days == days_old


def test_every_band_is_present_even_when_nothing_is_owed():
    report = build_ageing(_NOW, [])

    assert [band.label for band in report.bands] == [label for label, _ in AGE_BANDS]
    assert report.total == Decimal("0.00")
    assert all(band.count == 0 for band in report.bands)


def test_band_totals_add_up_to_the_whole():
    report = build_ageing(
        _NOW, [_owing(5, "100.00"), _owing(45, "200.00"), _owing(200, "300.00")]
    )

    assert report.total == Decimal("600.00")
    assert sum(band.total for band in report.bands) == report.total
    assert sum(band.share for band in report.bands) == Decimal("100.0")


def test_the_oldest_debt_is_listed_first():
    report = build_ageing(_NOW, [_owing(5), _owing(200), _owing(45)])

    assert [line.age_days for line in report.lines] == [200, 45, 5]


def test_a_document_with_no_party_is_still_listed():
    report = build_ageing(_NOW, [_owing(5, party=None)])

    assert report.lines[0].party == UNNAMED_PARTY


# ---------------------------------------------------------------- end to end


def _stocked_item(uow, admin_session, name: str = "A4 Sheet"):
    return CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name=name, unit="sheets")
    )


def _buy(uow, admin_session, item, quantity: int, price: str, number: str, supplier_id=None):
    return CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no=number,
            supplier_id=supplier_id,
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=quantity,
                    unit_price=Decimal(price),
                )
            ],
        )
    )


def _sell(uow, admin_session, item, quantity: int, price: str, number: str,
          customer_id=None, paid: str | None = None):
    payments = []
    if paid is not None:
        payments = [
            SalePaymentCommand(
                amount=Decimal(paid),
                received_by_user_id=admin_session.get_user().user_id,
            )
        ]
    return CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no=number,
            customer_id=customer_id,
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=quantity,
                    unit_price=Decimal(price),
                )
            ],
            payments=payments,
        )
    )


def _profit(uow, session):
    return GetProfitAndLossUseCase(uow, session).execute(
        ReportQuery(start=_ALL_TIME, end=_FAR_FUTURE)
    )


def test_a_sale_records_the_weighted_average_of_what_its_stock_cost(uow, admin_session):
    item = _stocked_item(uow, admin_session)
    _buy(uow, admin_session, item, 100, "10.00", "PUR-1")
    _buy(uow, admin_session, item, 100, "20.00", "PUR-2")

    sale = _sell(uow, admin_session, item, 50, "40.00", "INV-1")

    # Weighted by quantity, not an average of the two prices.
    assert sale.items[0].unit_cost == Decimal("15.00")
    assert sale.items[0].cost_amount == Decimal("750.00")


def test_buying_the_item_again_does_not_rewrite_an_old_sales_cost(uow, admin_session):
    """The whole reason the cost is stored on the line: a statement handed
    over last month must not change because of what happened this month."""
    item = _stocked_item(uow, admin_session)
    _buy(uow, admin_session, item, 100, "10.00", "PUR-1")
    _sell(uow, admin_session, item, 10, "40.00", "INV-1")

    _buy(uow, admin_session, item, 100, "90.00", "PUR-2")

    with uow as u:
        sale = u.sales.get_by_invoice_no("INV-1")
    assert sale.items[0].unit_cost == Decimal("10.00")


def test_recording_a_payment_does_not_erase_the_cost_on_the_lines(uow, admin_session):
    """`update()` rebuilds the sale's lines from the entity and merges them
    by id, so a cost the entity does not carry is a cost wiped off the
    row. Nothing else in the app would notice."""
    item = _stocked_item(uow, admin_session)
    _buy(uow, admin_session, item, 100, "10.00", "PUR-1")
    sale = _sell(uow, admin_session, item, 10, "40.00", "INV-1")

    RecordSalePaymentUseCase(uow, admin_session).execute(
        RecordSalePaymentCommand(
            sale_id=sale.id,
            amount=Decimal("100.00"),
            received_by_user_id=admin_session.get_user().user_id,
        )
    )

    with uow as u:
        settled = u.sales.get_by_invoice_no("INV-1")
    assert [line.unit_cost for line in settled.items] == [Decimal("10.00")]


def test_two_lines_of_the_same_item_on_one_invoice_take_the_same_cost(uow, admin_session):
    item = _stocked_item(uow, admin_session)
    _buy(uow, admin_session, item, 100, "10.00", "PUR-1")

    sale = CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-1",
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=5,
                    unit_price=Decimal("40.00"),
                ),
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=5,
                    unit_price=Decimal("45.00"),
                ),
            ],
        )
    )

    assert [line.unit_cost for line in sale.items] == [Decimal("10.00"), Decimal("10.00")]


def test_a_sale_of_stock_never_bought_has_no_cost_and_the_report_says_so(uow, admin_session):
    item = _stocked_item(uow, admin_session)
    # Stocked by a count-in rather than a purchase, so nothing anywhere
    # records what it cost.
    RecordInventoryMovementUseCase(uow, admin_session).execute(
        InventoryMovementCommand(
            movement_type=MovementType.ADJUSTMENT,
            item_type=ItemType.INVENTORY_ITEM,
            inventory_item_id=item.id,
            quantity_change=100,
            reason="Opening stock count",
        )
    )

    sale = _sell(uow, admin_session, item, 10, "40.00", "INV-1")
    assert sale.items[0].unit_cost is None

    report = _profit(uow, admin_session)
    assert report.is_complete is False
    assert report.uncosted_lines == 1
    assert report.uncosted_revenue == Decimal("400.00")
    assert report.cost_of_goods_sold == Decimal("0.00")


def test_the_profit_and_loss_adds_up_end_to_end(uow, admin_session):
    item = _stocked_item(uow, admin_session)
    _buy(uow, admin_session, item, 100, "10.00", "PUR-1")
    _sell(uow, admin_session, item, 10, "40.00", "INV-1")
    CreateExpenseUseCase(uow, admin_session).execute(
        CreateExpenseCommand(expense_name="Rent", amount=Decimal("150.00"))
    )

    report = _profit(uow, admin_session)

    assert report.revenue == Decimal("400.00")
    assert report.cost_of_goods_sold == Decimal("100.00")
    assert report.gross_profit == Decimal("300.00")
    assert report.expenses_total == Decimal("150.00")
    assert report.net_profit == Decimal("150.00")
    # Bought a thousand pounds of stock and still made money: the point of
    # the whole exercise.
    assert report.stock_bought == Decimal("1000.00")
    assert report.is_complete is True


def test_item_profitability_names_and_totals_what_was_sold(uow, admin_session):
    item = _stocked_item(uow, admin_session, "Art Card")
    _buy(uow, admin_session, item, 100, "10.00", "PUR-1")
    _sell(uow, admin_session, item, 10, "40.00", "INV-1")

    report = GetItemProfitabilityUseCase(uow, admin_session).execute(
        ReportQuery(start=_ALL_TIME, end=_FAR_FUTURE)
    )

    row = report.rows[0]
    assert (row.name, row.quantity_sold) == ("Art Card", 10)
    assert row.revenue == Decimal("400.00")
    assert row.cost == Decimal("100.00")
    assert row.profit == Decimal("300.00")
    assert row.margin == Decimal("75.0")


def test_ageing_lists_only_what_is_still_unpaid(uow, admin_session):
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders")
    )
    item = _stocked_item(uow, admin_session)
    _buy(uow, admin_session, item, 100, "10.00", "PUR-1")

    _sell(uow, admin_session, item, 5, "40.00", "INV-PAID",
          customer_id=customer.id, paid="200.00")
    _sell(uow, admin_session, item, 5, "40.00", "INV-OWING", customer_id=customer.id)

    report = GetAgeingUseCase(uow, admin_session, source=ReceivablesSource()).execute(
        AgeingQuery(as_at=datetime.now())
    )

    assert [line.reference for line in report.lines] == ["INV-OWING"]
    assert report.total == Decimal("200.00")
    assert report.lines[0].party == "Ahmad Traders"


def test_payables_ageing_reads_purchases_not_sales(uow, admin_session):
    supplier = CreateSupplierUseCase(uow, admin_session).execute(
        CreateSupplierCommand(name="Paper Mill")
    )
    item = _stocked_item(uow, admin_session)
    _buy(uow, admin_session, item, 100, "10.00", "PUR-1", supplier_id=supplier.id)

    report = GetAgeingUseCase(uow, admin_session, source=PayablesSource()).execute(
        AgeingQuery(as_at=datetime.now())
    )

    assert [line.reference for line in report.lines] == ["PUR-1"]
    assert report.total == Decimal("1000.00")
    assert report.lines[0].party == "Paper Mill"


def test_a_report_counts_every_document_not_the_first_page(uow, admin_session):
    """The screen this replaced fetched two thousand rows and summed them,
    so it under-reported silently past that. Nothing here takes a limit."""
    for index in range(60):
        CreateExpenseUseCase(uow, admin_session).execute(
            CreateExpenseCommand(expense_name=f"Expense {index}", amount=Decimal("10.00"))
        )

    report = _profit(uow, admin_session)

    assert report.expense_count == 60
    assert report.expenses_total == Decimal("600.00")


@pytest.mark.parametrize(
    "report",
    ["profit_and_loss", "item_profitability", "ageing"],
)
def test_reports_refuse_a_user_without_permission(uow, staff_session, report):
    """A staff user genuinely lacks VIEW_REPORTS. The screen this replaced
    never checked."""
    use_cases = {
        "profit_and_loss": lambda: GetProfitAndLossUseCase(uow, staff_session).execute(
            ReportQuery(start=_ALL_TIME, end=_FAR_FUTURE)
        ),
        "item_profitability": lambda: GetItemProfitabilityUseCase(uow, staff_session).execute(
            ReportQuery(start=_ALL_TIME, end=_FAR_FUTURE)
        ),
        "ageing": lambda: GetAgeingUseCase(
            uow, staff_session, source=ReceivablesSource()
        ).execute(AgeingQuery(as_at=datetime.now())),
    }

    with pytest.raises(AuthorizationError):
        use_cases[report]()
