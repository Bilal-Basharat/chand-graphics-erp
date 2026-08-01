from __future__ import annotations

from app.application.dto.commands import CreateCardCommand, InventoryMovementCommand
from app.application.use_cases.cards import CreateCardUseCase, GetCardByNumberUseCase
from app.application.use_cases.inventory_movements import RecordInventoryMovementUseCase
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from decimal import Decimal


def test_record_inventory_adjustment(uow, admin_session):
    card = CreateCardUseCase(uow, admin_session).execute(
        CreateCardCommand(
            card_number="1111",
            name="1111 Card",
            purchase_price=Decimal("10.00"),
            selling_price=Decimal("20.00"),
            current_stock=100,
            minimum_stock=20,
        )
    )

    movement = RecordInventoryMovementUseCase(uow, admin_session).execute(
        InventoryMovementCommand(
            movement_type=MovementType.ADJUSTMENT,
            item_type=ItemType.CARD,
            quantity_change=-5,
            card_id=card.id,
            reason="Damaged cards",
        )
    )

    assert movement.id is not None
    assert movement.previous_stock == 100
    assert movement.resulting_stock == 95

    fresh_card = GetCardByNumberUseCase(uow).execute("1111")
    assert fresh_card is not None
    assert fresh_card.current_stock == 95