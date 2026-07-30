from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import CreatePurchaseCommand, CreateSupplierCommand, PurchaseItemCommand
from app.application.use_cases.cards import CreateCardUseCase
from app.application.use_cases.master_data import CreateSupplierUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase, GetPurchaseByNoUseCase
from app.domain.enums.item_type import ItemType
from app.application.dto.commands import CreateCardCommand


def test_create_purchase_increases_card_stock_and_stores_snapshots(uow):
    supplier = CreateSupplierUseCase(uow).execute(
        CreateSupplierCommand(name="Main Branch")
    )

    card = CreateCardUseCase(uow).execute(
        CreateCardCommand(
            card_number="1111",
            name="1111 Card",
            purchase_price=Decimal("10.00"),
            selling_price=Decimal("15.00"),
            current_stock=100,
            minimum_stock=20,
        )
    )

    purchase = CreatePurchaseUseCase(uow).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-0001",
            supplier_id=supplier.id,
            discount_amount=Decimal("0.00"),
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.CARD,
                    card_id=card.id,
                    quantity=25,
                    unit_price=Decimal("10.00"),
                )
            ],
            payments=[],
        )
    )

    assert purchase.id is not None
    assert purchase.subtotal == Decimal("250.00")
    assert purchase.grand_total == Decimal("250.00")
    assert purchase.paid_amount == Decimal("0.00")
    assert purchase.balance_amount == Decimal("250.00")

    assert len(purchase.items) == 1
    assert purchase.items[0].previous_stock == 100
    assert purchase.items[0].resulting_stock == 125

    fresh_card = CreateCardUseCase(uow).uow.cards.get_by_card_number("1111")
    assert fresh_card is not None
    assert fresh_card.current_stock == 125

    loaded_purchase = GetPurchaseByNoUseCase(uow).execute("PUR-0001")
    assert loaded_purchase is not None
    assert loaded_purchase.purchase_no == "PUR-0001"
    assert len(loaded_purchase.items) == 1