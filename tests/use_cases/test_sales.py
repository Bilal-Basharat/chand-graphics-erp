from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import CreateCardCommand, CreateSaleCommand, SaleItemCommand
from app.application.use_cases.cards import CreateCardUseCase, GetCardByNumberUseCase
from app.application.use_cases.sales import CreateSaleUseCase, GetSaleByInvoiceNoUseCase
from app.domain.enums.item_type import ItemType


def test_create_sale_decreases_card_stock_and_stores_snapshots(uow, admin_session):
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

    sale = CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-0001",
            discount_amount=Decimal("0.00"),
            items=[
                SaleItemCommand(
                    item_type=ItemType.CARD,
                    card_id=card.id,
                    quantity=30,
                    unit_price=Decimal("20.00"),
                )
            ],
            payments=[],
        )
    )

    assert sale.id is not None
    assert sale.subtotal == Decimal("600.00")
    assert sale.grand_total == Decimal("600.00")
    assert sale.paid_amount == Decimal("0.00")
    assert sale.balance_amount == Decimal("600.00")

    assert len(sale.items) == 1
    assert sale.items[0].previous_stock == 100
    assert sale.items[0].resulting_stock == 70

    fresh_card = GetCardByNumberUseCase(uow).execute("1111")
    assert fresh_card is not None
    assert fresh_card.current_stock == 70

    loaded_sale = GetSaleByInvoiceNoUseCase(uow).execute("INV-0001")
    assert loaded_sale is not None
    assert loaded_sale.invoice_no == "INV-0001"
    assert len(loaded_sale.items) == 1