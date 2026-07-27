from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType

@dataclass(slots=True)
class DateRangeQuery:
    start: datetime
    end: datetime
    limit: int = 200


@dataclass(slots=True)
class CreateCabinetCommand:
    code: str
    description: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class CreateCardCommand:
    card_number: str
    name: str
    purchase_price: Decimal
    selling_price: Decimal
    minimum_stock: int = 0
    current_stock: int = 0
    cabinet_id: int | None = None
    description: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class CreateInventoryItemCommand:
    name: str
    purchase_price: Decimal
    selling_price: Decimal
    minimum_stock: int = 0
    current_stock: int = 0
    description: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class CreateCustomerCommand:
    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class CreateSupplierCommand:
    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class CreatePaymentMethodCommand:
    name: str


@dataclass(slots=True)
class CreateExpenseCategoryCommand:
    name: str
    description: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class CreateCompanySettingsCommand:
    company_name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    currency: str = "PKR"
    logo_path: str | None = None
    invoice_footer: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class CreateExpenseCommand:
    expense_name: str
    amount: Decimal | None = None
    category_id: int | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
    remarks: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class PurchaseItemCommand:
    item_type: ItemType
    quantity: int
    unit_price: Decimal
    card_id: int | None = None
    inventory_item_id: int | None = None
    note: str | None = None


@dataclass(slots=True)
class PurchasePaymentCommand:
    amount: Decimal
    payment_method_id: int
    paid_by_user_id: int
    reference_no: str | None = None
    note: str | None = None


@dataclass(slots=True)
class CreatePurchaseCommand:
    purchase_no: str
    supplier_id: int | None = None
    reference_no: str | None = None
    note: str | None = None
    discount_amount: Decimal = Decimal("0.00")
    created_by_user_id: int | None = None
    items: list[PurchaseItemCommand] = field(default_factory=list)
    payments: list[PurchasePaymentCommand] = field(default_factory=list)


@dataclass(slots=True)
class SaleItemCommand:
    item_type: ItemType
    quantity: int
    unit_price: Decimal
    card_id: int | None = None
    inventory_item_id: int | None = None
    note: str | None = None


@dataclass(slots=True)
class SalePaymentCommand:
    amount: Decimal
    payment_method_id: int
    received_by_user_id: int
    reference_no: str | None = None
    note: str | None = None


@dataclass(slots=True)
class CreateSaleCommand:
    invoice_no: str
    customer_id: int | None = None
    note: str | None = None
    discount_amount: Decimal = Decimal("0.00")
    created_by_user_id: int | None = None
    items: list[SaleItemCommand] = field(default_factory=list)
    payments: list[SalePaymentCommand] = field(default_factory=list)


@dataclass(slots=True)
class InventoryMovementCommand:
    movement_type: MovementType
    item_type: ItemType
    quantity_change: int
    card_id: int | None = None
    inventory_item_id: int | None = None
    source_document_type: str | None = None
    source_document_id: int | None = None
    reference_no: str | None = None
    reason: str | None = None
    note: str | None = None
    created_by_user_id: int | None = None