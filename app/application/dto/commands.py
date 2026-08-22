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
class CreateCategoryCommand:
    name: str
    description: str | None = None


@dataclass(slots=True)
class UpdateCategoryCommand:
    id: int
    name: str
    description: str | None = None


@dataclass(slots=True)
class CreateProductCommand:
    """A product and, with it, the one SKU it starts life with.

    A product with nothing under it could not be bought, sold or counted,
    so there is no step where one exists on its own. The SKU's fields are
    here rather than in a second command for the same reason the screen
    has no second step: a shopkeeper adding "A4 Ivory 250gsm" is adding
    one thing.
    """

    name: str
    category_id: int | None = None
    """None means the default category — see `Category.DEFAULT_CATEGORY_NAME`."""

    unit: str | None = None
    """The SKU's base unit: the word its stock is counted in."""

    minimum_stock: Decimal = Decimal("0")
    description: str | None = None
    cabinet_id: int | None = None


@dataclass(slots=True)
class UpdateProductCommand:
    """Rename a product, or file it somewhere else.

    Renaming reaches its SKU when it has exactly one — see
    `UpdateProductUseCase`. `category_id` of None leaves the shelf alone
    rather than clearing it, because a product always has one.
    """

    id: int
    name: str | None = None
    category_id: int | None = None


@dataclass(slots=True)
class SkuUnitCommand:
    """One alternate unit of a SKU, as a screen states it.

    "Box = 288" — a name and how many base units one of them is worth.
    An `id` where the unit already exists, so a factor can be corrected
    without the unit being replaced and the documents that used it losing
    what they name.
    """

    name: str
    factor: Decimal
    id: int | None = None


@dataclass(slots=True)
class CreateInventoryItemCommand:
    """A SKU. Normally the one a new product is created with; otherwise a
    further variant of a product that already exists.

    `product_id` of None means "make a product for this", which is what a
    lone item has always meant and what keeps every caller that predates
    products working unchanged.
    """

    name: str
    minimum_stock: Decimal = Decimal("0")
    current_stock: Decimal = Decimal("0")
    description: str | None = None
    cabinet_id: int | None = None
    unit: str | None = None
    product_id: int | None = None

    units: tuple[SkuUnitCommand, ...] = ()
    """Its alternate units, as the whole list rather than as add/remove
    instructions: the dialog shows a list and the shopkeeper edits it,
    and turning that back into a sequence of operations in the view
    would be business logic in a widget.

    Carried on the same command as the item so both land in one unit of
    work — a SKU and the ways it is counted are one thing to save.
    """


@dataclass(slots=True)
class UpdateInventoryItemCommand:
    """Corrections to an item's catalogue details.

    Stock is absent on purpose: it moves through purchases, sales and
    stock adjustments, and a field that silently overwrote it here would
    be a second, untracked way to change the same number.
    """

    id: int
    name: str
    minimum_stock: Decimal = Decimal("0")
    description: str | None = None
    cabinet_id: int | None = None
    unit: str | None = None

    units: tuple[SkuUnitCommand, ...] = ()
    """See `CreateInventoryItemCommand.units` — the complete list, saved
    with the item."""

    category_id: int | None = None
    """Which shelf to file its product on.

    A product's, not an item's — and only meaningful where this item is
    the only one of its product, which is exactly when the catalogue
    shows the two as one row and one form. None leaves the shelf alone.
    """


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
    quantity: Decimal
    """How many, in the unit named by `uom_id`."""

    unit_price: Decimal
    """What one of *those* costs. A price is a price for the unit it was
    quoted in."""

    inventory_item_id: int | None = None
    uom_id: int | None = None
    """Which of the SKU's alternate units the quantity is in, or None for
    its base unit."""

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
    quantity: Decimal
    """How many, in the unit named by `uom_id`."""

    unit_price: Decimal
    """What one of *those* costs. A price is a price for the unit it was
    quoted in."""

    inventory_item_id: int | None = None
    uom_id: int | None = None
    """Which of the SKU's alternate units the quantity is in, or None for
    its base unit."""

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
    quantity_change: Decimal
    """How far the count moves, with its sign, in the unit named by
    `uom_id`. Negative takes stock off the shelf."""

    inventory_item_id: int | None = None
    uom_id: int | None = None
    """Which of the SKU's alternate units, or None for its base unit."""
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
    quantity: Decimal
    """In the unit that line was traded in. A return carries no unit of
    its own: it is a reversal, and one measured differently from what it
    reverses could not be bounded by it."""


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
