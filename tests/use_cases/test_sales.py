from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    PurchaseItemCommand,
    SaleItemCommand,
)
from app.application.use_cases.inventory_items import (
    CreateInventoryItemUseCase,
    GetInventoryItemByNameUseCase,
)
from app.application.use_cases.purchases import CreatePurchaseUseCase
from app.application.use_cases.sales import CreateSaleUseCase, GetSaleByInvoiceNoUseCase
from app.domain.enums.item_type import ItemType


def test_create_sale_decreases_stock_and_stores_snapshots(uow, admin_session):
    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(
            name="A4 Ivory Sheet 250gsm",
            unit="sheets",
            current_stock=0,
            minimum_stock=20,
        )
    )

    # items start at zero stock; bring stock to 100 via a purchase before selling from it
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

    sale = CreateSaleUseCase(uow, admin_session).execute(
        CreateSaleCommand(
            invoice_no="INV-0001",
            discount_amount=Decimal("0.00"),
            items=[
                SaleItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
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

    fresh_item = GetInventoryItemByNameUseCase(uow).execute("A4 Ivory Sheet 250gsm")
    assert fresh_item is not None
    assert fresh_item.current_stock == 70

    loaded_sale = GetSaleByInvoiceNoUseCase(uow).execute("INV-0001")
    assert loaded_sale is not None
    assert loaded_sale.invoice_no == "INV-0001"
    assert len(loaded_sale.items) == 1
