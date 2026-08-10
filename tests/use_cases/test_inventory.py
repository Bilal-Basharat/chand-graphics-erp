from __future__ import annotations

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    InventoryMovementCommand,
    PurchaseItemCommand,
)
from app.application.use_cases.inventory_items import (
    CreateInventoryItemUseCase,
    GetInventoryItemByNameUseCase,
)
from app.application.use_cases.inventory_movements import RecordInventoryMovementUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from decimal import Decimal


def test_record_inventory_adjustment(uow, admin_session):
    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(
            name="A4 Ivory Sheet 250gsm",
            unit="sheets",
            current_stock=0,
            minimum_stock=20,
        )
    )

    # items start at zero stock; bring stock to 100 via a purchase before adjusting it down
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-SETUP",
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
                    quantity=100,
                    unit_price=Decimal("10.00"),
                )
            ],
            payments=[],
        )
    )

    movement = RecordInventoryMovementUseCase(uow, admin_session).execute(
        InventoryMovementCommand(
            movement_type=MovementType.ADJUSTMENT,
            item_type=ItemType.INVENTORY_ITEM,
            quantity_change=-5,
            inventory_item_id=item.id,
            reason="Damaged sheets",
        )
    )

    assert movement.id is not None
    assert movement.previous_stock == 100
    assert movement.resulting_stock == 95

    fresh_item = GetInventoryItemByNameUseCase(uow).execute("A4 Ivory Sheet 250gsm")
    assert fresh_item is not None
    assert fresh_item.current_stock == 95
