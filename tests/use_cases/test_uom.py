"""
Buying by the box and selling by the piece.

Every one of these is really the same assertion from a different angle:
the shelf is counted in one unit, whatever unit a document was written
in, and what a document says it traded never changes afterwards.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    CreateProductCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    InventoryMovementCommand,
    PurchaseItemCommand,
    RecordPurchaseReturnCommand,
    RecordSaleReturnCommand,
    ReturnedLineCommand,
    SaleItemCommand,
    SkuUnitCommand,
    UpdateInventoryItemCommand,
)
from app.application.dto.queries import CataloguePageQuery
from app.application.exceptions import NotFoundError
from app.application.use_cases.catalogue import (
    CreateProductUseCase,
    GetActiveSkuUnitsUseCase,
    GetSkuUnitsUseCase,
    PageCatalogueUseCase,
)
from app.application.use_cases.inventory_items import (
    CreateInventoryItemUseCase,
    UpdateInventoryItemUseCase,
)
from app.application.use_cases.inventory_movements import RecordInventoryMovementUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.application.use_cases.returns import (
    RecordPurchaseReturnUseCase,
    RecordSaleReturnUseCase,
)
from app.application.use_cases.sales import CreateSaleUseCase
from app.domain.entities.sku_unit import SkuUnit
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType

BOX = Decimal("288")
"""One box of A4, in pieces. The example the whole feature exists for."""


@pytest.fixture()
def sku(uow, admin_session):
    """One item, counted in pieces, with a Box and a Packet beside it."""
    CreateProductUseCase(uow, admin_session).execute(
        CreateProductCommand(name="A4 Ivory 80gsm", unit="Piece")
    )
    item = _item_named(uow, admin_session, "A4 Ivory 80gsm")
    _set_units(
        uow,
        admin_session,
        item,
        SkuUnitCommand(name="Box", factor=BOX),
        SkuUnitCommand(name="Packet", factor=Decimal("24")),
    )
    return item


def _set_units(uow, session, sku, *specs):
    """A SKU's alternate units, set the way the item form sets them.

    Through the item's own command rather than a use case of their own:
    units belong to the SKU and are saved with it, in one unit of work.
    """
    return UpdateInventoryItemUseCase(uow, session).execute(
        UpdateInventoryItemCommand(
            id=sku.id,
            name=sku.name,
            minimum_stock=sku.minimum_stock,
            description=sku.description,
            cabinet_id=sku.cabinet_id,
            unit=sku.unit,
            units=tuple(specs),
        )
    )


def _item_named(uow, session, name: str):
    page = PageCatalogueUseCase(uow, session).execute(CataloguePageQuery(search=name))
    return next(row.sku for row in page.rows if row.name == name)


def _unit(uow, session, sku_id: int, name: str) -> int:
    return next(
        unit.id for unit in GetSkuUnitsUseCase(uow, session).execute(sku_id) if unit.name == name
    )


def _stock(uow, session, sku_id: int) -> Decimal:
    with uow as unit_of_work:
        return unit_of_work.inventory_items.get_by_id(sku_id).current_stock


def _buy(uow, session, sku_id, quantity, price, *, uom_id=None, number="PUR-1"):
    return CreatePurchaseUseCase(uow, session).execute(
        CreatePurchaseCommand(
            purchase_no=number,
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=sku_id,
                    quantity=Decimal(quantity),
                    unit_price=Decimal(price),
                    uom_id=uom_id,
                )
            ],
            payments=[],
        )
    )


def _sell(uow, session, sku_id, quantity, price, *, uom_id=None, number="INV-1"):
    return CreateSaleUseCase(uow, session).execute(
        CreateSaleCommand(
            invoice_no=number,
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=sku_id,
                    quantity=Decimal(quantity),
                    unit_price=Decimal(price),
                    uom_id=uom_id,
                )
            ],
            payments=[],
        )
    )


# ------------------------------------------------------------------ the units


def test_an_item_starts_with_no_alternate_units(uow, admin_session):
    CreateProductUseCase(uow, admin_session).execute(
        CreateProductCommand(name="Gold Foil", unit="rolls")
    )
    item = _item_named(uow, admin_session, "Gold Foil")

    assert GetSkuUnitsUseCase(uow, admin_session).execute(item.id) == []


def test_a_unit_says_how_many_base_units_it_is_worth(uow, admin_session, sku):
    units = {unit.name: unit.factor for unit in GetSkuUnitsUseCase(uow, admin_session).execute(sku.id)}

    assert units == {"Box": Decimal("288.0000"), "Packet": Decimal("24.0000")}


def test_a_unit_worth_nothing_is_refused():
    with pytest.raises(ValueError):
        SkuUnit(sku_id=1, name="Box", factor=Decimal("0"))
    with pytest.raises(ValueError):
        SkuUnit(sku_id=1, name="Box", factor=Decimal("-3"))


def test_a_unit_cannot_be_called_what_the_item_is_already_counted_in(uow, admin_session, sku):
    with pytest.raises(ValueError):
        _set_units(uow, admin_session, sku, SkuUnitCommand(name="piece", factor=BOX)
        )


def test_a_unit_a_document_used_is_retired_rather_than_deleted(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "1", "5000.00", uom_id=box)

    _set_units(uow, admin_session, sku, SkuUnitCommand(name="Packet", factor=Decimal("24"))
    )

    remaining = {unit.name: unit.is_active for unit in GetSkuUnitsUseCase(uow, admin_session).execute(sku.id)}
    assert remaining == {"Box": False, "Packet": True}


def test_a_unit_nothing_used_is_removed_outright(uow, admin_session, sku):
    _set_units(uow, admin_session, sku, SkuUnitCommand(name="Box", factor=BOX)
    )

    assert [unit.name for unit in GetSkuUnitsUseCase(uow, admin_session).execute(sku.id)] == ["Box"]


def test_a_retired_unit_is_not_offered_for_a_new_line(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "1", "5000.00", uom_id=box)
    _set_units(uow, admin_session, sku, )

    assert GetActiveSkuUnitsUseCase(uow, admin_session).execute(sku.id) == []
    with pytest.raises(ValueError):
        _sell(uow, admin_session, sku.id, "1", "20.00", uom_id=box)


def test_a_unit_belonging_to_another_item_is_refused(uow, admin_session, sku):
    other = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Gold Foil", unit="rolls")
    )
    box = _unit(uow, admin_session, sku.id, "Box")

    with pytest.raises(NotFoundError):
        _buy(uow, admin_session, other.id, "1", "100.00", uom_id=box)


# ------------------------------------------------------------------- the shelf


def test_buying_in_boxes_puts_pieces_on_the_shelf(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")

    _buy(uow, admin_session, sku.id, "10", "5000.00", uom_id=box)

    assert _stock(uow, admin_session, sku.id) == Decimal("2880.0000")


def test_a_line_with_no_unit_is_counted_in_the_item_s_own(uow, admin_session, sku):
    _buy(uow, admin_session, sku.id, "500", "10.00")

    assert _stock(uow, admin_session, sku.id) == Decimal("500.0000")


def test_selling_a_piece_out_of_a_box_leaves_the_rest(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "1", "5000.00", uom_id=box)

    _sell(uow, admin_session, sku.id, "1", "25.00")

    assert _stock(uow, admin_session, sku.id) == Decimal("287.0000")


@pytest.mark.parametrize("sold", ["0.5", "0.25", "0.125"])
def test_a_fraction_of_a_base_unit_can_be_sold(uow, admin_session, sku, sold):
    _buy(uow, admin_session, sku.id, "10", "10.00")

    _sell(uow, admin_session, sku.id, sold, "25.00")

    assert _stock(uow, admin_session, sku.id) == Decimal("10") - Decimal(sold)


def test_quarters_sold_three_times_come_to_three_quarters(uow, admin_session, sku):
    """The reason quantities are Decimal and not float."""
    _buy(uow, admin_session, sku.id, "10", "10.00")

    for number in range(3):
        _sell(uow, admin_session, sku.id, "0.25", "25.00", number=f"INV-{number}")

    assert _stock(uow, admin_session, sku.id) == Decimal("9.2500")


def test_boxes_packets_and_pieces_all_land_on_one_count(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    packet = _unit(uow, admin_session, sku.id, "Packet")

    _buy(uow, admin_session, sku.id, "2", "5000.00", uom_id=box, number="PUR-1")
    _buy(uow, admin_session, sku.id, "3", "480.00", uom_id=packet, number="PUR-2")
    _buy(uow, admin_session, sku.id, "12", "20.00", number="PUR-3")

    assert _stock(uow, admin_session, sku.id) == Decimal("2") * BOX + Decimal("72") + Decimal("12")


def test_an_adjustment_can_be_counted_in_boxes_too(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "2", "5000.00", uom_id=box)

    movement = RecordInventoryMovementUseCase(uow, admin_session).execute(
        InventoryMovementCommand(
            movement_type=MovementType.DAMAGE,
            item_type=ItemType.INVENTORY_ITEM,
            inventory_item_id=sku.id,
            quantity_change=Decimal("-1"),
            uom_id=box,
            reason="Water damage",
        )
    )

    assert movement.quantity == Decimal("1.0000")
    assert movement.base_quantity == BOX
    assert movement.quantity_change == -BOX
    assert _stock(uow, admin_session, sku.id) == BOX


# ------------------------------------------------------------- what is written


def test_a_line_keeps_both_the_quantity_typed_and_what_it_came_to(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")

    purchase = _buy(uow, admin_session, sku.id, "10", "5000.00", uom_id=box)

    line = purchase.items[0]
    assert line.quantity == Decimal("10.0000")
    assert line.uom_id == box
    assert line.base_quantity == Decimal("2880.0000")
    assert line.total_amount == Decimal("50000.0000")


def test_changing_a_factor_does_not_move_a_document_already_written(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    purchase = _buy(uow, admin_session, sku.id, "10", "5000.00", uom_id=box)
    before = _stock(uow, admin_session, sku.id)

    _set_units(uow, admin_session, sku, SkuUnitCommand(id=box, name="Box", factor=Decimal("144")))

    with uow as unit_of_work:
        stored = unit_of_work.purchases.get_by_id(purchase.id).items[0]
    assert stored.base_quantity == Decimal("2880.0000")
    assert _stock(uow, admin_session, sku.id) == before


# ---------------------------------------------------------------- the costing


def test_the_cost_of_one_piece_is_read_off_a_purchase_in_boxes(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "10", "2880.00", uom_id=box)

    sale = _sell(uow, admin_session, sku.id, "1", "25.00")

    # 10 boxes at 2,880 is 28,800 for 2,880 pieces — ten each.
    assert sale.items[0].unit_cost == Decimal("10.00")
    assert sale.items[0].cost_amount == Decimal("10.0000")


def test_deliveries_in_different_units_average_against_each_other(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "1", "2880.00", uom_id=box, number="PUR-1")
    _buy(uow, admin_session, sku.id, "288", "20.00", number="PUR-2")

    sale = _sell(uow, admin_session, sku.id, "1", "40.00")

    # 2,880 + 5,760 spent on 576 pieces.
    assert sale.items[0].unit_cost == Decimal("15.00")


def test_a_sale_in_boxes_costs_a_box_and_not_a_piece(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "10", "2880.00", uom_id=box)

    sale = _sell(uow, admin_session, sku.id, "2", "4000.00", uom_id=box)

    line = sale.items[0]
    assert line.unit_cost == Decimal("10.00")
    assert line.cost_amount == Decimal("5760.0000")
    assert line.total_amount == Decimal("8000.0000")


def test_margin_by_item_counts_base_units_and_costs_them(uow, admin_session, sku):
    from datetime import timedelta

    from app.application.dto.queries import ReportQuery
    from app.application.use_cases.reports import GetItemProfitabilityUseCase
    from app.shared.datetimes import now_pkt

    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "10", "2880.00", uom_id=box)
    _sell(uow, admin_session, sku.id, "1", "4000.00", uom_id=box)

    now = now_pkt()
    report = GetItemProfitabilityUseCase(uow, admin_session).execute(
        ReportQuery(start=now - timedelta(days=1), end=now + timedelta(days=1))
    )

    row = next(row for row in report.rows if row.name == "A4 Ivory 80gsm")
    assert row.quantity_sold == BOX
    assert row.revenue == Decimal("4000.00")
    assert row.cost == Decimal("2880.00")


# ----------------------------------------------------------------- the returns


def test_a_return_puts_back_what_the_line_took_off(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "10", "2880.00", uom_id=box)
    sale = _sell(uow, admin_session, sku.id, "2", "4000.00", uom_id=box)
    after_sale = _stock(uow, admin_session, sku.id)

    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=Decimal("1"))],
            reason="Wrong weight",
        )
    )

    assert _stock(uow, admin_session, sku.id) == after_sale + BOX


def test_a_return_uses_the_conversion_of_the_line_it_reverses(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "10", "2880.00", uom_id=box)
    sale = _sell(uow, admin_session, sku.id, "2", "4000.00", uom_id=box)
    after_sale = _stock(uow, admin_session, sku.id)

    # The box is redefined between the sale and the return.
    _set_units(uow, admin_session, sku, SkuUnitCommand(id=box, name="Box", factor=Decimal("144"))
    )
    RecordSaleReturnUseCase(uow, admin_session).execute(
        RecordSaleReturnCommand(
            return_no="SR-1",
            sale_id=sale.id,
            lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=Decimal("1"))],
            reason="Wrong weight",
        )
    )

    assert _stock(uow, admin_session, sku.id) == after_sale + BOX


def test_a_return_cannot_send_back_more_than_the_line_sold(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "10", "2880.00", uom_id=box)
    sale = _sell(uow, admin_session, sku.id, "2", "4000.00", uom_id=box)

    with pytest.raises(ValueError):
        RecordSaleReturnUseCase(uow, admin_session).execute(
            RecordSaleReturnCommand(
                return_no="SR-1",
                sale_id=sale.id,
                lines=[ReturnedLineCommand(line_id=sale.items[0].id, quantity=Decimal("3"))],
                reason="Too many",
            )
        )


def test_returning_a_purchase_takes_the_boxes_back_off_the_shelf(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    purchase = _buy(uow, admin_session, sku.id, "10", "2880.00", uom_id=box)

    RecordPurchaseReturnUseCase(uow, admin_session).execute(
        RecordPurchaseReturnCommand(
            return_no="PR-1",
            purchase_id=purchase.id,
            lines=[ReturnedLineCommand(line_id=purchase.items[0].id, quantity=Decimal("2"))],
            reason="Damaged in transit",
        )
    )

    assert _stock(uow, admin_session, sku.id) == Decimal("8") * BOX


def test_a_returned_delivery_comes_off_the_average_in_base_units(uow, admin_session, sku):
    box = _unit(uow, admin_session, sku.id, "Box")
    _buy(uow, admin_session, sku.id, "1", "2880.00", uom_id=box, number="PUR-1")
    dear = _buy(uow, admin_session, sku.id, "288", "40.00", number="PUR-2")

    RecordPurchaseReturnUseCase(uow, admin_session).execute(
        RecordPurchaseReturnCommand(
            return_no="PR-1",
            purchase_id=dear.id,
            lines=[ReturnedLineCommand(line_id=dear.items[0].id, quantity=Decimal("288"))],
            reason="Sent back",
        )
    )
    sale = _sell(uow, admin_session, sku.id, "1", "25.00")

    # Only the boxed delivery is left: 2,880 for 288 pieces.
    assert sale.items[0].unit_cost == Decimal("10.00")
