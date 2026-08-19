"""
Goods coming back, and the four records that have to agree afterwards.

The case at the top of this file is the bug these use cases were written
for: an item that was bought and never sold could be "returned by a
customer", and the shop ended up with more stock than it had ever owned.
Nothing in the old model could refuse it, because a return named an item
rather than the sale it reversed.

Everything else here follows from anchoring a return to a line — what may
come back, how much of it is left after a first return, and what money
may honestly go back with it.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    PurchaseItemCommand,
    RecordPurchaseReturnCommand,
    RecordSaleReturnCommand,
    ReturnedLineCommand,
    SaleItemCommand,
    SalePaymentCommand,
)
from app.application.dto.queries import ReturnableDocumentQuery
from app.application.use_cases.inventory_items import (
    CreateInventoryItemUseCase,
    GetInventoryItemByNameUseCase,
)
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.application.use_cases.returns import (
    GetReturnablePurchaseUseCase,
    GetReturnableSaleUseCase,
    RecordPurchaseReturnUseCase,
    RecordSaleReturnUseCase,
)
from app.application.use_cases.sales import CreateSaleUseCase, GetSaleByInvoiceNoUseCase
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType

ITEM = "A4 70gsm"


def _item(uow, session, name: str = ITEM):
    return CreateInventoryItemUseCase(uow, session).execute(
        CreateInventoryItemCommand(name=name, unit="sheets", current_stock=0, minimum_stock=0)
    )


def _buy(uow, session, item, quantity: int, *, number="PUR-1", price="10.00", paid=None):
    return CreatePurchaseUseCase(uow, session).execute(
        CreatePurchaseCommand(
            purchase_no=number,
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=quantity,
                    unit_price=Decimal(price),
                )
            ],
            payments=paid or [],
        )
    )


def _sell(uow, session, item, quantity: int, *, number="INV-1", price="20.00",
          customer_id=None, paid=None):
    return CreateSaleUseCase(uow, session).execute(
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
            payments=paid or [],
        )
    )


def _sell_two(uow, session, first, second, *, number="INV-1", customer_id=None, paid=None):
    """One invoice carrying two different items — what a return of more
    than one thing at a time is recorded against."""
    return CreateSaleUseCase(uow, session).execute(
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
                for item, quantity, price in (
                    (first, 10, "20.00"),
                    (second, 10, "30.00"),
                )
            ],
            payments=paid or [],
        )
    )


def _stock(uow, name: str = ITEM) -> int:
    return GetInventoryItemByNameUseCase(uow).execute(name).current_stock


# ------------------------------------------------------------- the reported bug


def test_stock_that_was_never_sold_cannot_be_returned_by_a_customer(uow, admin_session):
    """The bug this whole module exists for.

    An item bought a hundred times and never sold had no sale behind it,
    yet a return could still be recorded against the item and take the
    count to a hundred and ten. Now a return names a line, and an item
    that was never sold has no line to name.
    """
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)

    sale = _sell(uow, admin_session, item, 40)

    with pytest.raises(ValueError):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=sale.id,
                lines=[
                    # A line from no invoice at all: there is nothing on
                    # this sale that says these goods went out.
                    ReturnedLineCommand(line_id=sale.items[0].id + 999, quantity=10)
                ],
            )
        )

    assert _stock(uow) == 60


def test_a_return_cannot_exceed_what_its_line_sold(uow, admin_session):
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)

    with pytest.raises(ValueError, match="Only 40"):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=sale.id,
                lines=[
                    ReturnedLineCommand(
                        line_id=sale.items[0].id,
                        quantity=41,
                    )
                ],
            )
        )

    assert _stock(uow) == 60


def test_partial_returns_add_up_against_the_same_line(uow, admin_session):
    """Two returns of ten against a line of forty leave twenty, not thirty."""
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)
    line = sale.items[0]
    use_case = RecordSaleReturnUseCase(uow, admin_session)

    for number in ("SR-1", "SR-2"):
        use_case.execute(
            RecordSaleReturnCommand(
                return_no=number,
                sale_id=sale.id,
                lines=[ReturnedLineCommand(line_id=line.id, quantity=10)],
            )
        )

    with pytest.raises(ValueError, match="Only 20"):
        use_case.execute(
            RecordSaleReturnCommand(
                return_no="SR-3",
                sale_id=sale.id,
                lines=[ReturnedLineCommand(line_id=line.id, quantity=21)],
            )
        )

    assert _stock(uow) == 80


def test_several_items_come_back_as_one_return(uow, admin_session):
    """The whole point of a return having lines.

    A customer handing back two things is one trip to the counter: one
    number, one refund, one line on their account — and two counts on the
    shelf going up.
    """
    first, second = _item(uow, admin_session), _item(uow, admin_session, "A3 80gsm")
    _buy(uow, admin_session, first, 100)
    _buy(uow, admin_session, second, 100, number="PUR-2")
    sale = _sell_two(uow, admin_session, first, second)

    saved = RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[
                ReturnedLineCommand(line_id=sale.items[0].id, quantity=4),
                ReturnedLineCommand(line_id=sale.items[1].id, quantity=3),
            ],
        )
    )

    assert len(saved.items) == 2
    # 4 at 20.00 and 3 at 30.00.
    assert saved.return_amount == Decimal("170.00")
    assert _stock(uow) == 94
    assert _stock(uow, "A3 80gsm") == 93

    invoice = GetSaleByInvoiceNoUseCase(uow, admin_session).execute("INV-1")
    assert invoice.returned_amount == Decimal("170.00")

    # One movement per item: the register is read down its item column,
    # and two items are two counts changing.
    with uow as u:
        movements = u.inventory_movements.find_all_by(
            "movement_type", MovementType.RETURN
        )
    assert sorted(movement.quantity for movement in movements) == [3, 4]
    assert {movement.reference_no for movement in movements} == {"SR-1 · INV-1"}


def test_one_line_named_twice_is_capped_as_one(uow, admin_session):
    """Two goes at the same line are one line coming back.

    Checked as a total, not one at a time: 25 and 20 off a line of 40 are
    each under the cap and together over it.
    """
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)

    with pytest.raises(ValueError, match="Only 40"):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=sale.id,
                lines=[
                    ReturnedLineCommand(line_id=sale.items[0].id, quantity=25),
                    ReturnedLineCommand(line_id=sale.items[0].id, quantity=20),
                ],
            )
        )

    assert _stock(uow) == 60


def test_a_return_with_no_lines_is_refused(uow, admin_session):
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)

    with pytest.raises(ValueError):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(return_no="SR-1", sale_id=sale.id, lines=[])
        )


def test_nothing_moves_when_a_later_line_is_refused(uow, admin_session):
    """A return is one act. Its second line failing must not leave the
    first line's goods back on the shelf."""
    first, second = _item(uow, admin_session), _item(uow, admin_session, "A3 80gsm")
    _buy(uow, admin_session, first, 100)
    _buy(uow, admin_session, second, 100, number="PUR-2")
    sale = _sell_two(uow, admin_session, first, second)

    with pytest.raises(ValueError):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=sale.id,
                lines=[
                    ReturnedLineCommand(line_id=sale.items[0].id, quantity=5),
                    ReturnedLineCommand(line_id=sale.items[1].id, quantity=99),
                ],
            )
        )

    assert _stock(uow) == 90
    assert _stock(uow, "A3 80gsm") == 90


def test_a_line_from_another_invoice_cannot_be_returned_against_this_one(uow, admin_session):
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    first = _sell(uow, admin_session, item, 10, number="INV-1")
    second = _sell(uow, admin_session, item, 10, number="INV-2")

    with pytest.raises(ValueError, match="not on this invoice"):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=second.id,
                lines=[
                    ReturnedLineCommand(
                        line_id=first.items[0].id,
                        quantity=5,
                    )
                ],
            )
        )


# ------------------------------------------------------------ what a return does


def test_a_customer_return_raises_stock_and_lowers_the_invoice(uow, admin_session):
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)

    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=10)],
        )
    )

    assert _stock(uow) == 70

    updated = GetSaleByInvoiceNoUseCase(uow).execute("INV-1")
    assert updated.grand_total == Decimal("800.00")  # what was invoiced stands
    assert updated.returned_amount == Decimal("200.00")
    assert updated.net_total == Decimal("600.00")
    assert updated.balance_amount == Decimal("600.00")


def test_a_return_writes_a_movement_naming_the_document_it_came_off(uow, admin_session):
    """The stock register keeps its row — now with something behind it."""
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)

    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=10)],
        )
    )

    with uow as u:
        movements = u.inventory_movements.find_all_by("movement_type", MovementType.RETURN)

    assert len(movements) == 1
    movement = movements[0]
    assert movement.source_document_type == "SALE_RETURN"
    assert movement.source_document_id is not None
    assert "SR-1" in movement.reference_no and "INV-1" in movement.reference_no
    assert (movement.previous_stock, movement.resulting_stock) == (60, 70)


def test_a_refund_cannot_exceed_the_money_actually_received(uow, admin_session):
    """Otherwise a credit sale could be refunded in cash the shop never took."""
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)  # nothing paid

    with pytest.raises(ValueError, match="available to refund"):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=sale.id,
                lines=[
                    ReturnedLineCommand(
                        line_id=sale.items[0].id,
                        quantity=10,
                    )
                ],
                refund_amount=Decimal("200.00"),
            )
        )

    assert _stock(uow) == 60


def test_a_refund_cannot_exceed_what_the_goods_were_worth(uow, admin_session, staff_session):
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(
        uow,
        admin_session,
        item,
        40,
        paid=[SalePaymentCommand(amount=Decimal("800.00"), received_by_user_id=1)],
    )

    with pytest.raises(ValueError, match="were worth"):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=sale.id,
                lines=[
                    ReturnedLineCommand(
                        line_id=sale.items[0].id,
                        quantity=10,
                    )
                ],
                refund_amount=Decimal("201.00"),
            )
        )


def test_a_refund_leaves_the_invoice_settled_and_a_credit_leaves_it_owing_back(
    uow, admin_session
):
    """The two halves of a return, and the difference between them.

    Refund the value and the customer is square. Leave it as credit and
    the balance goes negative — which is correct, and is the whole reason
    the goods and the money are recorded apart.
    """
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 200)
    sale = _sell(
        uow,
        admin_session,
        item,
        40,
        paid=[SalePaymentCommand(amount=Decimal("800.00"), received_by_user_id=1)],
    )
    line = sale.items[0]
    use_case = RecordSaleReturnUseCase(uow, admin_session)

    use_case.execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[
                ReturnedLineCommand(
                    line_id=line.id,
                    quantity=10,
                )
            ],
            refund_amount=Decimal("200.00"),
        )
    )
    assert GetSaleByInvoiceNoUseCase(uow).execute("INV-1").balance_amount == Decimal("0.00")

    use_case.execute(
        RecordSaleReturnCommand(
            return_no="SR-2",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=line.id, quantity=10)],
        )
    )
    settled = GetSaleByInvoiceNoUseCase(uow).execute("INV-1")
    assert settled.returned_amount == Decimal("400.00")
    assert settled.refunded_amount == Decimal("200.00")
    assert settled.balance_amount == Decimal("-200.00")


def test_two_returns_cannot_share_a_number(uow, admin_session):
    from app.application.exceptions import DuplicateEntityError

    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)
    use_case = RecordSaleReturnUseCase(uow, admin_session)

    use_case.execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=5)],
        )
    )
    with pytest.raises(DuplicateEntityError):
        use_case.execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=sale.id,
                lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=5)],
            )
        )


# ------------------------------------------------------------ going the other way


def test_a_purchase_return_lowers_stock_and_the_bill(uow, admin_session):
    item = _item(uow, admin_session)
    purchase = _buy(uow, admin_session, item, 100)

    RecordPurchaseReturnUseCase(uow, admin_session).execute(
        RecordPurchaseReturnCommand(
            return_no="PR-1",
            purchase_id=purchase.id,
            lines=[
                ReturnedLineCommand(
                    line_id=purchase.items[0].id,
                    quantity=10,
                )
            ],
        )
    )

    assert _stock(uow) == 90
    with uow as u:
        updated = u.purchases.get_by_purchase_no("PUR-1")
    assert updated.returned_amount == Decimal("100.00")
    assert updated.net_total == Decimal("900.00")


def test_stock_already_sold_on_cannot_also_go_back_to_the_supplier(uow, admin_session):
    item = _item(uow, admin_session)
    purchase = _buy(uow, admin_session, item, 100)
    _sell(uow, admin_session, item, 95)

    with pytest.raises(ValueError):
        RecordPurchaseReturnUseCase(uow, admin_session).execute(
            RecordPurchaseReturnCommand(
                return_no="PR-1",
                purchase_id=purchase.id,
                lines=[
                    ReturnedLineCommand(
                        line_id=purchase.items[0].id,
                        quantity=10,
                    )
                ],
            )
        )

    assert _stock(uow) == 5


# --------------------------------------------------------- what the dialog reads


def test_a_returnable_sale_reports_what_is_left_on_each_line(uow, admin_session):
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)

    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=15)],
        )
    )

    document = GetReturnableSaleUseCase(uow, admin_session).execute(
        ReturnableDocumentQuery(reference="INV-1")
    )

    assert document.reference == "INV-1"
    assert document.party_name == "Walk-in customer"
    assert document.has_party is False
    line = document.lines[0]
    assert (line.quantity, line.returned, line.remaining) == (40, 15, 25)
    assert line.label == ITEM
    assert document.refundable == Decimal("0.00")


def test_a_fully_returned_line_is_no_longer_offered(uow, admin_session):
    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)
    sale = _sell(uow, admin_session, item, 40)

    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=40)],
        )
    )

    document = GetReturnableSaleUseCase(uow, admin_session).execute(
        ReturnableDocumentQuery(document_id=sale.id)
    )
    assert document.lines[0].remaining == 0
    assert document.returnable_lines == ()


def test_a_returnable_purchase_is_read_the_same_way(uow, admin_session):
    item = _item(uow, admin_session)
    purchase = _buy(uow, admin_session, item, 100)

    document = GetReturnablePurchaseUseCase(uow, admin_session).execute(
        ReturnableDocumentQuery(reference="PUR-1")
    )
    assert document.reference == "PUR-1"
    assert document.lines[0].remaining == 100
    assert document.party_name == "No supplier"


def test_a_document_that_is_not_there_is_reported_as_missing(uow, admin_session):
    from app.application.exceptions import NotFoundError

    with pytest.raises(NotFoundError, match="INV-NOPE"):
        GetReturnableSaleUseCase(uow, admin_session).execute(
            ReturnableDocumentQuery(reference="INV-NOPE")
        )


def test_a_return_cannot_be_recorded_as_a_bare_stock_movement(uow, admin_session):
    """The other half of the fix.

    The dialog no longer offers RETURN, but "the form does not offer it"
    is not a rule — this is. A return names the document it reverses or it
    is not recorded at all.
    """
    from app.application.dto.commands import InventoryMovementCommand
    from app.application.use_cases.inventory_movements import (
        RecordInventoryMovementUseCase,
    )

    item = _item(uow, admin_session)
    _buy(uow, admin_session, item, 100)

    with pytest.raises(ValueError, match="must be recorded against"):
        RecordInventoryMovementUseCase(uow, admin_session).execute(
            InventoryMovementCommand(
                movement_type=MovementType.RETURN,
                item_type=ItemType.INVENTORY_ITEM,
                inventory_item_id=item.id,
                quantity_change=10,
            )
        )

    assert _stock(uow) == 100
