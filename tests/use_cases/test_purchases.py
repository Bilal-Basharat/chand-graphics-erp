from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    CreatePurchaseCommand,
    CreateSupplierCommand,
    PurchaseItemCommand,
)
from app.application.use_cases.inventory_items import (
    CreateInventoryItemUseCase,
    GetInventoryItemByNameUseCase,
)
from app.application.use_cases.master_data import CreateSupplierUseCase
from app.application.use_cases.purchases import CreatePurchaseUseCase, GetPurchaseByNoUseCase
from app.domain.enums.item_type import ItemType


def test_create_purchase_increases_stock_and_stores_snapshots(uow, admin_session):
    supplier = CreateSupplierUseCase(uow, admin_session).execute(
        CreateSupplierCommand(name="Main Branch")
    )

    item = CreateInventoryItemUseCase(uow, admin_session).execute(
        CreateInventoryItemCommand(
            name="A4 Ivory Sheet 250gsm",
            unit="sheets",
            current_stock=0,
            minimum_stock=20,
        )
    )

    purchase = CreatePurchaseUseCase(uow, admin_session).execute(
        CreatePurchaseCommand(
            purchase_no="PUR-0001",
            supplier_id=supplier.id,
            discount_amount=Decimal("0.00"),
            items=[
                PurchaseItemCommand(
                    item_type=ItemType.INVENTORY_ITEM,
                    inventory_item_id=item.id,
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
    assert purchase.items[0].previous_stock == 0
    assert purchase.items[0].resulting_stock == 25

    fresh_item = GetInventoryItemByNameUseCase(uow).execute("A4 Ivory Sheet 250gsm")
    assert fresh_item is not None
    assert fresh_item.current_stock == 25
    # the price lives on the purchase line, not on the catalogue record
    assert purchase.items[0].unit_price == Decimal("10.00")

    loaded_purchase = GetPurchaseByNoUseCase(uow).execute("PUR-0001")
    assert loaded_purchase is not None
    assert loaded_purchase.purchase_no == "PUR-0001"
    assert len(loaded_purchase.items) == 1
