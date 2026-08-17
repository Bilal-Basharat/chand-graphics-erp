from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.application.dto.commands import (
    CreateCustomerCommand,
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    PurchaseItemCommand,
    SaleItemCommand,
    SalePaymentCommand,
)
from app.application.dto.queries import DocumentPageQuery
from app.application.use_cases.inventory_items import CreateInventoryItemUseCase
from app.application.use_cases.master_data import CreateCustomerUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.application.use_cases.sales import CreateSaleUseCase, PageSalesUseCase
from app.domain.enums.item_type import ItemType
from app.domain.enums.payment_filter import PaymentFilter
from app.shared.datetimes import now_pkt

# A document list is the one place where what the screen shows and what
# the query filters on are two different things: the row prints totals the
# entity works out from its lines, and the query filters and sums the
# figures stored on the document. They have to agree, and nothing fails if
# they stop agreeing — the screen simply says something untrue.

ZERO = Decimal("0.00")


@pytest.fixture()
def period() -> dict:
    now = now_pkt()
    return {"start": now - timedelta(days=30), "end": now + timedelta(days=1)}


@pytest.fixture()
def stocked(uow, admin_session):
    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Art Card 250gsm", minimum_stock=10)
    )
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-STOCK",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=100_000,
                    unit_price=Decimal("10.00"),
                )
            ],
            payments=[],
        )
    )
    return item


def _sell(uow, admin_session, item, number: str, *, total: Decimal, paid: Decimal, customer=None):
    return CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no=number,
            customer_id=customer,
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=1,
                    unit_price=total,
                )
            ],
            payments=(
                [
                    SalePaymentCommand(
                        amount=paid,
                        received_by_user_id=admin_session.require_user_id(),
                    )
                ]
                if paid > ZERO
                else []
            ),
        )
    )


def _page(uow, admin_session, period, **kwargs):
    return PageSalesUseCase(uow, admin_session).execute(
        DocumentPageQuery(**period, **kwargs)
    )


# ------------------------------------------------- the two sets of figures


def test_the_totals_on_the_strip_are_the_ones_on_the_rows(uow, admin_session, stocked, period):
    """The strip's figures come from a SUM over the stored columns; the
    rows print what each document computes from its own lines. If the two
    ever disagree the screen is wrong in a way nothing reports."""
    _sell(uow, admin_session, stocked, "INV-1", total=Decimal("500.00"), paid=Decimal("200.00"))
    _sell(uow, admin_session, stocked, "INV-2", total=Decimal("300.00"), paid=ZERO)

    result = _page(uow, admin_session, period)

    assert result.totals.total == sum(sale.grand_total for sale in result.rows)
    assert result.totals.outstanding == sum(sale.balance_amount for sale in result.rows)
    assert (result.totals.total, result.totals.outstanding) == (
        Decimal("800.00"),
        Decimal("600.00"),
    )


def test_the_totals_describe_the_whole_period_not_the_page(uow, admin_session, stocked, period):
    """The reason they are computed rather than added up on screen."""
    for index in range(5):
        _sell(uow, admin_session, stocked, f"INV-{index}", total=Decimal("100.00"), paid=ZERO)

    result = _page(uow, admin_session, period, page_size=2)

    assert len(result.rows) == 2
    assert result.total == 5
    assert result.totals.total == Decimal("500.00")


def test_a_sale_still_carries_its_lines_so_its_row_can_show_a_total(
    uow, admin_session, stocked, period
):
    """A sale totals itself from its lines. Fetch a page without them and
    every row on screen reads 0.00 — with no error anywhere."""
    _sell(uow, admin_session, stocked, "INV-1", total=Decimal("750.00"), paid=ZERO)

    sale = _page(uow, admin_session, period).rows[0]

    assert sale.items
    assert sale.grand_total == Decimal("750.00")


# ------------------------------------------------------------- the filters


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [
        (PaymentFilter.NOT_FULLY_PAID, {"INV-NOTHING", "INV-PART"}),
        (PaymentFilter.NOTHING_PAID, {"INV-NOTHING"}),
        (PaymentFilter.PART_PAID, {"INV-PART"}),
        (PaymentFilter.FULLY_PAID, {"INV-PAID"}),
        (None, {"INV-NOTHING", "INV-PART", "INV-PAID"}),
    ],
)
def test_each_payment_filter_returns_what_its_label_claims(
    uow, admin_session, stocked, period, chosen, expected
):
    """All four states, because a filter the query cannot express does not
    fail — it stays in the dropdown and quietly hands back everything."""
    _sell(uow, admin_session, stocked, "INV-NOTHING", total=Decimal("100.00"), paid=ZERO)
    _sell(uow, admin_session, stocked, "INV-PART", total=Decimal("100.00"), paid=Decimal("40.00"))
    _sell(uow, admin_session, stocked, "INV-PAID", total=Decimal("100.00"), paid=Decimal("100.00"))

    result = _page(uow, admin_session, period, payment=chosen)

    assert {sale.invoice_no for sale in result.rows} == expected
    assert result.total == len(expected)


def test_a_filtered_total_is_of_the_filtered_documents(uow, admin_session, stocked, period):
    _sell(uow, admin_session, stocked, "INV-PAID", total=Decimal("100.00"), paid=Decimal("100.00"))
    _sell(uow, admin_session, stocked, "INV-OWING", total=Decimal("250.00"), paid=ZERO)

    result = _page(uow, admin_session, period, payment=PaymentFilter.NOT_FULLY_PAID)

    assert result.totals.total == Decimal("250.00")


# -------------------------------------------------------------- the period


def test_documents_outside_the_period_are_not_in_it(uow, admin_session, stocked):
    _sell(uow, admin_session, stocked, "INV-1", total=Decimal("100.00"), paid=ZERO)
    now = now_pkt()

    result = PageSalesUseCase(uow, admin_session).execute(
        DocumentPageQuery(start=now - timedelta(days=60), end=now - timedelta(days=30))
    )

    assert result.total == 0
    assert result.totals.total == ZERO


# -------------------------------------------------------------- the search


def test_an_invoice_is_found_by_the_customer_it_is_for(uow, admin_session, stocked, period):
    """People remember who owes them far more readily than which invoice
    number it was — and the placeholder on both screens promises it."""
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Al-Noor Printers")
    )
    _sell(
        uow, admin_session, stocked, "INV-1", total=Decimal("100.00"), paid=ZERO,
        customer=customer.id,
    )
    _sell(uow, admin_session, stocked, "INV-2", total=Decimal("100.00"), paid=ZERO)

    result = _page(uow, admin_session, period, search="Al-Noor")

    assert [sale.invoice_no for sale in result.rows] == ["INV-1"]


def test_an_invoice_is_found_by_its_number(uow, admin_session, stocked, period):
    _sell(uow, admin_session, stocked, "INV-4417", total=Decimal("100.00"), paid=ZERO)
    _sell(uow, admin_session, stocked, "INV-9002", total=Decimal("100.00"), paid=ZERO)

    result = _page(uow, admin_session, period, search="4417")

    assert [sale.invoice_no for sale in result.rows] == ["INV-4417"]


# --------------------------------------------------------------- the order


def test_a_document_list_opens_newest_first(uow, admin_session, stocked, period):
    """Not an aesthetic choice: a new invoice has to be on the page the
    user is returned to, or recording one looks like it did nothing."""
    for index in range(3):
        _sell(uow, admin_session, stocked, f"INV-{index}", total=Decimal("100.00"), paid=ZERO)

    result = _page(uow, admin_session, period)

    assert [sale.invoice_no for sale in result.rows] == ["INV-2", "INV-1", "INV-0"]


def test_sorting_by_a_column_orders_the_period_not_the_page(
    uow, admin_session, stocked, period
):
    for index, amount in enumerate(("300.00", "100.00", "200.00")):
        _sell(uow, admin_session, stocked, f"INV-{index}", total=Decimal(amount), paid=ZERO)

    result = _page(uow, admin_session, period, page_size=1, sort_field="total", sort_desc=True)

    assert [sale.invoice_no for sale in result.rows] == ["INV-0"]
