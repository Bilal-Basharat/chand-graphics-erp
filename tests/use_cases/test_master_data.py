from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import CreateCabinetCommand, CreateCardCommand
from app.application.use_cases.cards import CreateCardUseCase, GetCardByNumberUseCase, ListLowStockCardsUseCase
from app.application.use_cases.master_data import CreateCabinetUseCase


def test_create_cabinet_and_card(uow):
    cabinet = CreateCabinetUseCase(uow).execute(
        CreateCabinetCommand(code="A-01", description="Main cabinet")
    )

    card = CreateCardUseCase(uow).execute(
        CreateCardCommand(
            card_number="1111",
            name="1111 Card",
            purchase_price=Decimal("10.00"),
            selling_price=Decimal("15.00"),
            current_stock=100,
            minimum_stock=20,
            cabinet_id=cabinet.id,
            description="Wedding card batch",
        )
    )

    assert card.id is not None
    assert card.card_number == "1111"
    assert card.current_stock == 100

    found = GetCardByNumberUseCase(uow).execute("1111")
    assert found is not None
    assert found.card_number == "1111"
    assert found.cabinet_id == cabinet.id


def test_list_low_stock_cards(uow):
    CreateCardUseCase(uow).execute(
        CreateCardCommand(
            card_number="1111",
            name="1111 Card",
            purchase_price=Decimal("10.00"),
            selling_price=Decimal("15.00"),
            current_stock=50,
            minimum_stock=20,
        )
    )

    CreateCardUseCase(uow).execute(
        CreateCardCommand(
            card_number="2667",
            name="2667 Card",
            purchase_price=Decimal("12.00"),
            selling_price=Decimal("18.00"),
            current_stock=10,
            minimum_stock=20,
        )
    )

    low_stock = ListLowStockCardsUseCase(uow).execute(100)
    assert len(low_stock) == 1
    assert low_stock[0].card_number == "2667"