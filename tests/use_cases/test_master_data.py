from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateCardCommand,
    CreatePurchaseCommand,
    PurchaseItemCommand,
)
from app.application.use_cases.cards import CreateCardUseCase, GetCardByNumberUseCase, ListLowStockCardsUseCase
from app.application.use_cases.master_data import CreateCabinetUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.domain.enums.item_type import ItemType


def test_create_cabinet_and_card(uow, admin_session):
    cabinet = CreateCabinetUseCase(uow, admin_session).execute(
        CreateCabinetCommand(code="A-01", description="Main cabinet")
    )

    card = CreateCardUseCase(uow, admin_session).execute(
        CreateCardCommand(
            card_number="1111",
            name="1111 Card",
            current_stock=0,
            minimum_stock=20,
            cabinet_id=cabinet.id,
            description="Wedding card batch",
        )
    )

    assert card.id is not None
    assert card.card_number == "1111"
    assert card.current_stock == 0  # new cards always start at zero stock

    found = GetCardByNumberUseCase(uow).execute("1111")
    assert found is not None
    assert found.card_number == "1111"
    assert found.cabinet_id == cabinet.id


def test_list_low_stock_cards(uow, admin_session):
    card_a = CreateCardUseCase(uow, admin_session).execute(
        CreateCardCommand(
            card_number="1111",
            name="1111 Card",
            current_stock=0,
            minimum_stock=20,
        )
    )
    card_b = CreateCardUseCase(uow, admin_session).execute(
        CreateCardCommand(
            card_number="2667",
            name="2667 Card",
            current_stock=0,
            minimum_stock=20,
        )
    )

    # bring card_a comfortably above minimum, leave card_b below it
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-A",
            items=[PurchaseItemCommand(item_type=ItemType.CARD, card_id=card_a.id, quantity=50, unit_price=Decimal("10.00"))],
            payments=[],
        )
    )
    CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-B",
            items=[PurchaseItemCommand(item_type=ItemType.CARD, card_id=card_b.id, quantity=10, unit_price=Decimal("12.00"))],
            payments=[],
        )
    )

    low_stock = ListLowStockCardsUseCase(uow).execute(100)
    assert len(low_stock) == 1
    assert low_stock[0].card_number == "2667"