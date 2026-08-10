from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    PurchaseItemCommand,
)
from app.application.use_cases.inventory_items import (
    CreateInventoryItemUseCase,
    GetInventoryItemByNameUseCase,
    ListLowStockInventoryItemsUseCase,
)
from app.application.use_cases.master_data import CreateCabinetUseCase, DeleteCabinetUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.domain.enums.item_type import ItemType


def test_create_cabinet_and_item(uow, admin_session):
    cabinet = CreateCabinetUseCase(uow, admin_session).execute(
        CreateCabinetCommand(code="A-01", description="Main cabinet")
    )

    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(
            name="A4 Ivory Sheet 250gsm",
            unit="sheets",
            current_stock=0,
            minimum_stock=20,
            cabinet_id=cabinet.id,
            description="Opening stock",
        )
    )

    assert item.id is not None
    assert item.current_stock == 0  # new items always start at zero stock

    found = GetInventoryItemByNameUseCase(uow).execute("A4 Ivory Sheet 250gsm")
    assert found is not None
    assert found.cabinet_id == cabinet.id


def test_deleting_a_cabinet_unfiles_its_items(uow, admin_session):
    cabinet = CreateCabinetUseCase(uow, admin_session).execute(
        CreateCabinetCommand(code="A-01")
    )
    CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Blue ink", cabinet_id=cabinet.id)
    )

    unfiled = DeleteCabinetUseCase(uow, admin_session).execute(cabinet.id)

    assert unfiled == 1
    item = GetInventoryItemByNameUseCase(uow).execute("Blue ink")
    assert item is not None
    assert item.cabinet_id is None


def test_list_low_stock_items(uow, admin_session):
    stocked = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="A4 Ivory Sheet 250gsm", minimum_stock=20)
    )
    running_out = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(name="Blue ink", minimum_stock=20)
    )

    # bring one comfortably above minimum, leave the other below it
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-A",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=stocked.id,
                    quantity=50,
                    unit_price=Decimal("10.00"),
                )
            ],
            payments=[],
        )
    )
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-B",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=running_out.id,
                    quantity=10,
                    unit_price=Decimal("12.00"),
                )
            ],
            payments=[],
        )
    )

    low_stock = ListLowStockInventoryItemsUseCase(uow).execute(100)
    assert [item.name for item in low_stock] == ["Blue ink"]
