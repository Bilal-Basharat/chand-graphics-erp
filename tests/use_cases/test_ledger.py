from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.application.dto.commands import (
    CreateCustomerCommand,
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    CreateSupplierCommand,
    PurchaseItemCommand,
    RecordPurchaseReturnCommand,
    RecordSalePaymentCommand,
    RecordSaleReturnCommand,
    ReturnedLineCommand,
    SaleItemCommand,
    SalePaymentCommand,
)
from app.application.dto.queries import LedgerQuery
from app.application.exceptions import NotFoundError
from app.application.ledger.ports import LedgerDirection, LedgerEvent, LedgerParty
from app.application.ledger.sources import (
    PURCHASE,
    PURCHASE_RETURN,
    SALE,
    SALE_RETURN,
    CustomerLookup,
    PurchaseLedgerSource,
    SaleLedgerSource,
    SupplierLookup,
)
from app.application.use_cases.inventory_items import CreateInventoryItemUseCase
from app.application.use_cases.ledger import GetPartyLedgerUseCase, build_ledger
from app.application.use_cases.master_data import (
    CreateCustomerUseCase,
    CreateSupplierUseCase,
)
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.application.use_cases.returns import (
    RecordPurchaseReturnUseCase,
    RecordSaleReturnUseCase,
)
from app.application.use_cases.sales import CreateSaleUseCase, RecordSalePaymentUseCase
from app.domain.enums.item_type import ItemType

_ALL_TIME = datetime(1970, 1, 1)
_FAR_FUTURE = datetime(2999, 1, 1)


# ---------------------------------------------------------------- build_ledger


def _party(opening: str = "0.00") -> LedgerParty:
    return LedgerParty(id=1, name="Ahmad Traders", opening_balance=Decimal(opening))


def _event(day: int, direction: LedgerDirection, amount: str, reference: str = "X") -> LedgerEvent:
    return LedgerEvent(
        occurred_at=datetime(2026, 8, day),
        reference=reference,
        document_kind="test",
        detail="test",
        amount=Decimal(amount),
        direction=direction,
    )


def test_empty_ledger_closes_where_it_opened():
    ledger = build_ledger(_party("5000.00"), Decimal("5000.00"), [])

    assert ledger.lines == ()
    assert ledger.opening_balance == Decimal("5000.00")
    assert ledger.closing_balance == Decimal("5000.00")
    assert ledger.total_charges == Decimal("0.00")
    assert ledger.total_payments == Decimal("0.00")


def test_running_balance_follows_charges_and_payments():
    ledger = build_ledger(
        _party("5000.00"),
        Decimal("5000.00"),
        [
            _event(3, LedgerDirection.CHARGE, "12500.00", "INV-014"),
            _event(5, LedgerDirection.PAYMENT, "10000.00", "INV-014"),
        ],
    )

    assert [line.balance for line in ledger.lines] == [
        Decimal("17500.00"),
        Decimal("7500.00"),
    ]
    assert ledger.total_charges == Decimal("12500.00")
    assert ledger.total_payments == Decimal("10000.00")
    assert ledger.closing_balance == Decimal("7500.00")


def test_events_are_ordered_by_date_not_by_the_order_they_arrive():
    # Two sources cannot know about each other's dates, so the ledger has
    # to be the one that interleaves them.
    ledger = build_ledger(
        _party(),
        Decimal("0.00"),
        [
            _event(9, LedgerDirection.PAYMENT, "100.00", "late"),
            _event(1, LedgerDirection.CHARGE, "300.00", "early"),
        ],
    )

    assert [line.reference for line in ledger.lines] == ["early", "late"]
    assert [line.balance for line in ledger.lines] == [Decimal("300.00"), Decimal("200.00")]


def test_only_one_side_of_a_line_carries_a_figure():
    ledger = build_ledger(
        _party(),
        Decimal("0.00"),
        [
            _event(1, LedgerDirection.CHARGE, "300.00"),
            _event(2, LedgerDirection.PAYMENT, "300.00"),
        ],
    )

    charge, payment = ledger.lines
    assert (charge.charge, charge.payment) == (Decimal("300.00"), Decimal("0.00"))
    assert (payment.charge, payment.payment) == (Decimal("0.00"), Decimal("300.00"))


def test_a_party_in_credit_opens_negative_and_stays_consistent():
    ledger = build_ledger(
        _party("-2000.00"),
        Decimal("-2000.00"),
        [_event(4, LedgerDirection.CHARGE, "500.00")],
    )

    assert ledger.closing_balance == Decimal("-1500.00")


# ---------------------------------------------------------------- end to end


def _stocked_item(uow, admin_session, quantity: int = 500):
    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="A4 Ivory Sheet 250gsm", unit="sheets")
    )
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-STOCK",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=quantity,
                    unit_price=Decimal("10.00"),
                )
            ],
        )
    )
    return item


def _customer_ledger(uow, admin_session, customer_id: int, start=_ALL_TIME, end=_FAR_FUTURE):
    return GetPartyLedgerUseCase(
        uow,
        admin_session,
        party=CustomerLookup(),
        sources=(SaleLedgerSource(),),
    ).execute(LedgerQuery(party_id=customer_id, start=start, end=end))


def _supplier_ledger(uow, admin_session, supplier_id: int, start=_ALL_TIME, end=_FAR_FUTURE):
    return GetPartyLedgerUseCase(
        uow,
        admin_session,
        party=SupplierLookup(),
        sources=(PurchaseLedgerSource(),),
    ).execute(LedgerQuery(party_id=supplier_id, start=start, end=end))


def test_customer_ledger_reads_opening_balance_sales_and_payments(uow, admin_session):
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders", opening_balance=Decimal("5000.00"))
    )
    item = _stocked_item(uow, admin_session)

    sale = CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-0014",
            customer_id=customer.id,
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=25,
                    unit_price=Decimal("500.00"),
                )
            ],
            payments=[
                SalePaymentCommand(
                    amount=Decimal("10000.00"),
                    received_by_user_id=admin_session.get_user().user_id,
                )
            ],
        )
    )

    ledger = _customer_ledger(uow, admin_session, customer.id)

    assert ledger.party_name == "Ahmad Traders"
    assert ledger.opening_balance == Decimal("5000.00")
    assert ledger.total_charges == sale.grand_total == Decimal("12500.00")
    assert ledger.total_payments == Decimal("10000.00")
    assert ledger.closing_balance == Decimal("7500.00")

    charge, payment = ledger.lines
    assert (charge.detail, charge.reference) == ("Sale", "INV-0014")
    assert charge.balance == Decimal("17500.00")
    # A payment names the invoice it settled and how it was settled.
    assert payment.reference == "INV-0014"
    assert payment.detail == "Payment received · Cash"
    assert payment.balance == Decimal("7500.00")


def test_a_later_payment_lands_in_the_period_it_was_received(uow, admin_session):
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders")
    )
    item = _stocked_item(uow, admin_session)

    sale = CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-0015",
            customer_id=customer.id,
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=10,
                    unit_price=Decimal("100.00"),
                )
            ],
        )
    )
    RecordSalePaymentUseCase(uow, admin_session).execute(
        RecordSalePaymentCommand(
            sale_id=sale.id,
            amount=Decimal("400.00"),
            received_by_user_id=admin_session.get_user().user_id,
        )
    )

    # A window that opens after both were recorded: nothing is listed, and
    # both are folded into the opening balance instead.
    later = datetime.now() + timedelta(days=1)
    ledger = _customer_ledger(uow, admin_session, customer.id, start=later, end=_FAR_FUTURE)

    assert ledger.lines == ()
    assert ledger.opening_balance == Decimal("600.00")
    assert ledger.closing_balance == Decimal("600.00")


def test_walk_in_sales_belong_to_no_ledger(uow, admin_session):
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders")
    )
    item = _stocked_item(uow, admin_session)

    CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-WALKIN",
            customer_id=None,
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=1,
                    unit_price=Decimal("100.00"),
                )
            ],
        )
    )

    ledger = _customer_ledger(uow, admin_session, customer.id)

    assert ledger.lines == ()
    assert ledger.closing_balance == Decimal("0.00")


def test_supplier_ledger_counts_a_purchase_as_a_charge(uow, admin_session):
    supplier = CreateSupplierUseCase(uow, admin_session).execute(
        CreateSupplierCommand(name="Paper Mill", opening_balance=Decimal("1000.00"))
    )
    item = _stocked_item(uow, admin_session)

    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-0007",
            supplier_id=supplier.id,
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=20,
                    unit_price=Decimal("150.00"),
                )
            ],
        )
    )

    ledger = _supplier_ledger(uow, admin_session, supplier.id)

    assert ledger.opening_balance == Decimal("1000.00")
    assert ledger.total_charges == Decimal("3000.00")
    assert ledger.closing_balance == Decimal("4000.00")
    assert ledger.lines[0].detail == "Purchase"
    assert ledger.lines[0].reference == "PUR-0007"


def test_every_line_says_which_document_it_came_from(uow, admin_session):
    """The View button on a statement line opens that document, and this
    is what tells it which one to open — including on a payment line,
    which is a movement on the invoice it settled."""
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders")
    )
    supplier = CreateSupplierUseCase(uow, admin_session).execute(
        CreateSupplierCommand(name="Paper Mill")
    )
    item = _stocked_item(uow, admin_session)

    CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-0021",
            customer_id=customer.id,
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=10,
                    unit_price=Decimal("100.00"),
                )
            ],
            payments=[
                SalePaymentCommand(
                    amount=Decimal("400.00"),
                    received_by_user_id=admin_session.get_user().user_id,
                )
            ],
        )
    )
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-0021",
            supplier_id=supplier.id,
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=5,
                    unit_price=Decimal("50.00"),
                )
            ],
        )
    )

    customer_ledger = _customer_ledger(uow, admin_session, customer.id)
    supplier_ledger = _supplier_ledger(uow, admin_session, supplier.id)

    assert [line.document_kind for line in customer_ledger.lines] == [SALE, SALE]
    assert [line.document_kind for line in supplier_ledger.lines] == [PURCHASE]


def test_an_unknown_party_has_no_ledger(uow, admin_session):
    with pytest.raises(NotFoundError):
        _customer_ledger(uow, admin_session, 9999)


# ---------------------------------------------------------------- debit side

# Which column a figure lands in is the screen's to decide, and it is the
# one thing that differs between the two ledgers. These pin it down: the
# totals have to fall on the same side as the lines they add up, which is
# exactly what a second "which column" accessor got wrong.


def test_a_sale_is_a_debit_on_a_customers_statement():
    from app.presentation.views.account_ledger_view import CUSTOMER_LEDGER_PAGE

    debit, credit = CUSTOMER_LEDGER_PAGE.sides(Decimal("300.00"), Decimal("100.00"))
    assert (debit, credit) == (Decimal("300.00"), Decimal("100.00"))


def test_a_purchase_is_a_credit_on_a_suppliers_statement():
    from app.presentation.views.account_ledger_view import SUPPLIER_LEDGER_PAGE

    debit, credit = SUPPLIER_LEDGER_PAGE.sides(Decimal("300.00"), Decimal("100.00"))
    assert (debit, credit) == (Decimal("100.00"), Decimal("300.00"))


@pytest.mark.parametrize("page_name", ["CUSTOMER_LEDGER_PAGE", "SUPPLIER_LEDGER_PAGE"])
def test_statement_totals_land_on_the_same_side_as_their_lines(page_name):
    import app.presentation.views.account_ledger_view as view
    from app.presentation.records.builders import ledger_card

    page = getattr(view, page_name)
    ledger = build_ledger(
        _party("100.00"),
        Decimal("100.00"),
        [
            _event(1, LedgerDirection.CHARGE, "300.00"),
            _event(2, LedgerDirection.PAYMENT, "50.00"),
        ],
    )
    card = ledger_card(
        ledger,
        party_kind=page.party_noun,
        period_label="This month",
        sides=page.sides,
    )

    # Columns 3 and 4 of the statement are debit and credit; row 0 is the
    # opening balance, so the entries start at row 1.
    entries = card.sections[0].rows[1:]
    debit_column = [row[3] for row in entries]
    credit_column = [row[4] for row in entries]

    totals = {total.label: total.value for total in card.totals}
    # Exactly one figure per side across two lines, so the column and the
    # total have to read the same.
    assert totals["Debit"] == next(v for v in debit_column if v)
    assert totals["Credit"] == next(v for v in credit_column if v)
    # Named for what it is on both statements, not for who owes whom.
    assert totals["Closing balance"] == "350.00"


# ------------------------------------------------------------- goods coming back

# A return is two facts, and they move a balance opposite ways: the goods
# reduce what the party owes, the refund that may follow puts it back. The
# cases below pin both halves, and the one where a return has no account
# to reach at all.


def _returnable_sale(uow, admin_session, customer_id, *, paid: str | None = None):
    item = _stocked_item(uow, admin_session)
    payments = (
        [
            SalePaymentCommand(
                amount=Decimal(paid), received_by_user_id=admin_session.get_user().user_id
            )
        ]
        if paid
        else []
    )
    return CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-RET",
            customer_id=customer_id,
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=10,
                    unit_price=Decimal("100.00"),
                )
            ],
            payments=payments,
        )
    )


def test_goods_returned_credit_the_customers_account(uow, admin_session):
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders")
    )
    sale = _returnable_sale(uow, admin_session, customer.id)

    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=2)],
        )
    )

    ledger = _customer_ledger(uow, admin_session, customer.id)

    assert ledger.total_charges == Decimal("1000.00")
    assert ledger.total_payments == Decimal("200.00")
    assert ledger.closing_balance == Decimal("800.00")

    _charge, credit = ledger.lines
    assert credit.document_kind == SALE_RETURN
    assert credit.detail == "Goods returned · SR-1"
    # The invoice it came off, so the line opens that document.
    assert credit.reference == "INV-RET"


def test_a_refund_hands_the_money_back_and_leaves_the_balance_where_it_was(
    uow, admin_session
):
    """The two halves cancel: the customer has their goods' worth in cash
    rather than in credit, and owes exactly what they did before."""
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders")
    )
    sale = _returnable_sale(uow, admin_session, customer.id, paid="1000.00")
    before = _customer_ledger(uow, admin_session, customer.id).closing_balance

    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[
                ReturnedLineCommand(
                    line_id=sale.items[0].id,
                    quantity=2,
                )
            ],
            refund_amount=Decimal("200.00"),
        )
    )

    ledger = _customer_ledger(uow, admin_session, customer.id)
    assert ledger.closing_balance == before == Decimal("0.00")

    refund = ledger.lines[-1]
    assert refund.detail == "Refund paid · Cash"
    assert refund.charge == Decimal("200.00")
    assert refund.payment == Decimal("0.00")


def test_a_walk_in_return_reaches_no_ledger(uow, admin_session):
    """There is no account to credit, which is why the dialog offers to
    refund one in full."""
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders")
    )
    sale = _returnable_sale(uow, admin_session, None)

    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=2)],
        )
    )

    assert _customer_ledger(uow, admin_session, customer.id).lines == ()


def test_a_return_before_the_window_lands_in_the_opening_balance(uow, admin_session):
    """Otherwise the statement opens at a figure its own lines contradict."""
    customer = CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Ahmad Traders")
    )
    sale = _returnable_sale(uow, admin_session, customer.id)
    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=2)],
        )
    )

    later = datetime.now() + timedelta(days=1)
    ledger = _customer_ledger(uow, admin_session, customer.id, start=later, end=_FAR_FUTURE)

    assert ledger.lines == ()
    assert ledger.opening_balance == Decimal("800.00")
    assert ledger.closing_balance == Decimal("800.00")


def test_goods_sent_back_reduce_what_is_owed_to_a_supplier(uow, admin_session):
    supplier = CreateSupplierUseCase(uow, admin_session).execute(
        CreateSupplierCommand(name="Paper House")
    )
    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Board 300gsm", unit="sheets")
    )
    purchase = CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-RET",
            supplier_id=supplier.id,
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=50,
                    unit_price=Decimal("20.00"),
                )
            ],
        )
    )

    RecordPurchaseReturnUseCase(uow, admin_session).execute(
        RecordPurchaseReturnCommand(
            return_no="PR-1",
            purchase_id=purchase.id,
            lines=[
                ReturnedLineCommand(
                    line_id=purchase.items[0].id,
                    quantity=5,
                )
            ],
        )
    )

    ledger = _supplier_ledger(uow, admin_session, supplier.id)

    assert ledger.total_charges == Decimal("1000.00")
    assert ledger.total_payments == Decimal("100.00")
    assert ledger.closing_balance == Decimal("900.00")
    assert ledger.lines[-1].document_kind == PURCHASE_RETURN
    assert ledger.lines[-1].detail == "Goods sent back · PR-1"
