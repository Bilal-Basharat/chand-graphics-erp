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


@dataclass(slots=True)
class UpdateCabinetCommand:
    id: int
    code: str
    description: str | None = None


@dataclass(slots=True)
class CreateInventoryItemCommand:
    name: str
    minimum_stock: int = 0
    current_stock: int = 0
    description: str | None = None
    cabinet_id: int | None = None
    unit: str | None = None


@dataclass(slots=True)
class UpdateInventoryItemCommand:
    """Corrections to an item's catalogue details.

    Stock is absent on purpose: it moves through purchases, sales and
    stock adjustments, and a field that silently overwrote it here would
    be a second, untracked way to change the same number.
    """

    id: int
    name: str
    minimum_stock: int = 0
    description: str | None = None
    cabinet_id: int | None = None
    unit: str | None = None


@dataclass(slots=True)
class CreateCustomerCommand:
    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    opening_balance: Decimal = Decimal("0.00")


@dataclass(slots=True)
class UpdateCustomerCommand:
    id: int
    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    opening_balance: Decimal = Decimal("0.00")


@dataclass(slots=True)
class CreateSupplierCommand:
    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    opening_balance: Decimal = Decimal("0.00")


@dataclass(slots=True)
class UpdateSupplierCommand:
    id: int
    name: str
    phone: str | None = None
    address: str | None = None
    notes: str | None = None
    opening_balance: Decimal = Decimal("0.00")


@dataclass(slots=True)
class CreatePaymentMethodCommand:
    name: str


@dataclass(slots=True)
class UpdatePaymentMethodCommand:
    id: int
    name: str


@dataclass(slots=True)
class CreateExpenseCategoryCommand:
    name: str
    description: str | None = None


@dataclass(slots=True)
class UpdateExpenseCategoryCommand:
    id: int
    name: str
    description: str | None = None


@dataclass(slots=True)
class CreateCompanySettingsCommand:
    company_name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    currency: str = "PKR"
    logo_path: str | None = None
    invoice_footer: str | None = None


@dataclass(slots=True)
class UpdateCompanySettingsCommand:
    id: int
    company_name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    currency: str = "PKR"
    logo_path: str | None = None
    invoice_footer: str | None = None


@dataclass(slots=True)
class CreateExpenseCommand:
    expense_name: str
    amount: Decimal | None = None
    category_id: int | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
    remarks: str | None = None


@dataclass(slots=True)
class PurchaseItemCommand:
    item_type: ItemType
    quantity: int
    unit_price: Decimal
    inventory_item_id: int | None = None
    note: str | None = None


@dataclass(slots=True)
class PurchasePaymentCommand:
    amount: Decimal
    paid_by_user_id: int
    payment_method_id: int | None = None
    reference_no: str | None = None
    note: str | None = None


@dataclass(slots=True)
class RecordPurchasePaymentCommand:
    purchase_id: int
    amount: Decimal
    paid_by_user_id: int
    payment_method_id: int | None = None
    reference_no: str | None = None
    note: str | None = None


@dataclass(slots=True)
class CreatePurchaseCommand:
    purchase_no: str
    supplier_id: int | None = None
    reference_no: str | None = None
    note: str | None = None
    discount_amount: Decimal = Decimal("0.00")
    items: list[PurchaseItemCommand] = field(default_factory=list)
    payments: list[PurchasePaymentCommand] = field(default_factory=list)


@dataclass(slots=True)
class SaleItemCommand:
    item_type: ItemType
    quantity: int
    unit_price: Decimal
    inventory_item_id: int | None = None
    note: str | None = None


@dataclass(slots=True)
class SalePaymentCommand:
    amount: Decimal
    received_by_user_id: int
    payment_method_id: int | None = None
    reference_no: str | None = None
    note: str | None = None


@dataclass(slots=True)
class RecordSalePaymentCommand:
    sale_id: int
    amount: Decimal
    received_by_user_id: int
    payment_method_id: int | None = None
    reference_no: str | None = None
    note: str | None = None


@dataclass(slots=True)
class CreateSaleCommand:
    invoice_no: str
    customer_id: int | None = None
    note: str | None = None
    discount_amount: Decimal = Decimal("0.00")
    items: list[SaleItemCommand] = field(default_factory=list)
    payments: list[SalePaymentCommand] = field(default_factory=list)


@dataclass(slots=True)
class InventoryMovementCommand:
    movement_type: MovementType
    item_type: ItemType
    quantity_change: int
    inventory_item_id: int | None = None
    source_document_type: str | None = None
    source_document_id: int | None = None
    reference_no: str | None = None
    reason: str | None = None
    note: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class ReturnedLineCommand:
    """One line of a document, and how many of it are coming back.

    The line, not the item: what can come back is bounded by what that
    document sold or bought, and only a line id can say so. Shared by
    both kinds of return, which ask the same two things.
    """

    line_id: int
    quantity: int


@dataclass(slots=True)
class RecordSaleReturnCommand:
    """Goods off one sale, coming back over the counter.

    Several lines at once, because a customer hands back several things
    as one act — one return number, one decision about the refund.
    """

    return_no: str
    sale_id: int
    lines: list[ReturnedLineCommand]
    refund_amount: Decimal = Decimal("0.00")
    refund_method_id: int | None = None
    reason: str | None = None
    note: str | None = None
    created_by_user_id: int | None = None


@dataclass(slots=True)
class RecordPurchaseReturnCommand:
    """Goods off one purchase, going back to the supplier."""

    return_no: str
    purchase_id: int
    lines: list[ReturnedLineCommand]
    refund_amount: Decimal = Decimal("0.00")
    refund_method_id: int | None = None
    reason: str | None = None
    note: str | None = None
    created_by_user_id: int | None = None
