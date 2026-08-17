"""
Writing a dataset into the database the way the application would.

Every record here goes in through the same use case the screen behind it
uses, so seeded data obeys every rule the app enforces — stock is drawn
down, balances are computed, duplicate document numbers are refused — and
cannot drift into a shape the app itself could never produce.

The single exception is dating, which no use case offers and which is the
whole point of seeding for testing. See `backdating`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal
from itertools import chain

from app.application.auth.commands import (
    EnsureInitialAdminUserCommand,
    RecordLoginAuditCommand,
)
from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateCompanySettingsCommand,
    CreateCustomerCommand,
    CreateExpenseCategoryCommand,
    CreateExpenseCommand,
    CreateInventoryItemCommand,
    CreatePaymentMethodCommand,
    CreatePurchaseCommand,
    CreateSaleCommand,
    CreateSupplierCommand,
    InventoryMovementCommand,
    PurchaseItemCommand,
    PurchasePaymentCommand,
    SaleItemCommand,
    SalePaymentCommand,
)
from app.config import constants
from app.container import AppContainer
from app.domain.entities.user import User
from app.domain.enums.item_type import ItemType
from app.domain.enums.login_event_type import LoginEventType
from app.domain.enums.movement_type import MovementType
from app.infrastructure.db.database import engine
from app.shared.datetimes import now_pkt

from scripts.seed import backdating
from scripts.seed.backdating import Backdater
from scripts.seed.dataset import Dataset, DocumentSeed, ItemSeed, LineSeed

# Everything on a given day happens at the same hour, and a payment
# always lands after the document it settles. Fixed rather than random so
# two runs of the same seed produce byte-identical dates.
_DOCUMENT_AT = time(10, 30)
_PAYMENT_AT = time(15, 45)
_EXPENSE_AT = time(17, 0)
_MOVEMENT_AT = time(9, 15)
_SIGN_IN_AT = time(8, 45)


@dataclass(frozen=True, slots=True)
class SeedReport:
    customers: int = 0
    suppliers: int = 0
    items: int = 0
    purchases: int = 0
    sales: int = 0
    payments: int = 0
    expenses: int = 0
    movements: int = 0
    audits: int = 0
    dated_rows: int = 0


def sign_in_admin(container: AppContainer) -> User:
    """Make sure the default admin exists, and seed as them.

    The same account a first run creates, from the same constants —
    seeding must not invent a user the application would not.

    Deliberately not `ApplicationInitializer`: that also restores the
    saved session and writes a sign-in audit row, which would leave a
    seeding run showing up in the login history as a person.
    """
    container.ensure_initial_admin_use_case().execute(
        EnsureInitialAdminUserCommand(
            email=constants.DEFAULT_ADMIN_EMAIL,
            password=constants.DEFAULT_ADMIN_PASSWORD,
            full_name=constants.DEFAULT_ADMIN_FULL_NAME,
            role=constants.DEFAULT_ADMIN_ROLE,
        )
    )

    with container.create_uow() as uow:
        admin = uow.users.get_by_email(constants.DEFAULT_ADMIN_EMAIL)

    if admin is None:
        raise RuntimeError(f"No user '{constants.DEFAULT_ADMIN_EMAIL}' to seed as.")

    container.current_user_session.set_user(admin)
    return admin


@dataclass(slots=True)
class Seeder:
    container: AppContainer
    dataset: Dataset
    today: datetime = field(default_factory=now_pkt)

    _user_id: int = 0
    _now: datetime = field(default_factory=now_pkt)
    _backdater: Backdater = field(default_factory=Backdater)
    _cabinets: dict[str, int] = field(default_factory=dict)
    _methods: dict[str, int] = field(default_factory=dict)
    _categories: dict[str, int] = field(default_factory=dict)
    _customers: dict[str, int] = field(default_factory=dict)
    _suppliers: dict[str, int] = field(default_factory=dict)
    _items: dict[str, tuple[int, ItemSeed]] = field(default_factory=dict)
    _payments: int = 0
    _movements_recorded: int = 0

    def run(self) -> SeedReport:
        sign_in_admin(self.container)
        self._user_id = self.container.current_user_session.require_user_id()
        self._now = self.today
        self.today = self.today.replace(hour=0, minute=0, second=0, microsecond=0)

        self._company()
        self._master_data()
        self._documents()
        self._expenses()
        self._movements()
        self._audits()

        return SeedReport(
            customers=len(self._customers),
            suppliers=len(self._suppliers),
            items=len(self._items),
            purchases=len(self.dataset.purchases),
            sales=len(self.dataset.sales),
            payments=self._payments,
            expenses=len(self.dataset.expenses),
            movements=self._movements_recorded,
            audits=len(self.dataset.audits),
            dated_rows=self._backdater.apply(engine),
        )

    # ---------------- dates ----------------

    def _moment(self, days_ago: int, at: time) -> datetime:
        moment = datetime.combine((self.today - timedelta(days=days_ago)).date(), at)
        # Never later than the moment the seeding ran. A payment received
        # this afternoon, seeded this morning, would be stamped in the
        # future — and would then be missing from every screen whose
        # period ends at "now", including the one it was seeded for.
        return min(moment, self._now)

    def _oldest_day(self) -> int:
        """How far back the dataset reaches, so master data can predate it.

        A customer whose first invoice is five months old was not added to
        the books this morning.
        """
        days = chain(
            (document.days_ago for document in self.dataset.purchases),
            (document.days_ago for document in self.dataset.sales),
            (expense.days_ago for expense in self.dataset.expenses),
            (movement.days_ago for movement in self.dataset.movements),
        )
        return max(days, default=0) + 1

    # ---------------- master data ----------------

    def _company(self) -> None:
        # Only if the shop has not named itself yet: the letterhead is the
        # user's, and a seeding run has no business overwriting it.
        if self.container.get_company_settings_use_case().execute() is not None:
            return

        company = self.dataset.company
        self.container.create_company_settings_use_case().execute(
            CreateCompanySettingsCommand(
                company_name=company.company_name,
                phone=company.phone,
                email=company.email,
                address=company.address,
                invoice_footer=company.invoice_footer,
            )
        )

    def _master_data(self) -> None:
        opened = self._moment(self._oldest_day(), _DOCUMENT_AT)

        for cabinet in self.dataset.cabinets:
            record = self.container.create_cabinet_use_case().execute(
                CreateCabinetCommand(code=cabinet.name, description=cabinet.description)
            )
            self._cabinets[cabinet.name] = record.id
            self._backdater.row("cabinets", record.id, opened)

        for name in self.dataset.payment_methods:
            record = self.container.create_payment_method_use_case().execute(
                CreatePaymentMethodCommand(name=name)
            )
            self._methods[name] = record.id

        for category in self.dataset.expense_categories:
            record = self.container.create_expense_category_use_case().execute(
                CreateExpenseCategoryCommand(name=category.name, description=category.description)
            )
            self._categories[category.name] = record.id

        for customer in self.dataset.customers:
            record = self.container.create_customer_use_case().execute(
                CreateCustomerCommand(
                    name=customer.name,
                    phone=customer.phone,
                    address=customer.address,
                    notes=customer.notes,
                    opening_balance=customer.opening_balance,
                )
            )
            self._customers[customer.name] = record.id
            self._backdater.row("customers", record.id, opened)

        for supplier in self.dataset.suppliers:
            record = self.container.create_supplier_use_case().execute(
                CreateSupplierCommand(
                    name=supplier.name,
                    phone=supplier.phone,
                    address=supplier.address,
                    notes=supplier.notes,
                    opening_balance=supplier.opening_balance,
                )
            )
            self._suppliers[supplier.name] = record.id
            self._backdater.row("suppliers", record.id, opened)

        for item in self.dataset.items:
            record = self.container.create_inventory_item_use_case().execute(
                CreateInventoryItemCommand(
                    name=item.name,
                    unit=item.unit,
                    minimum_stock=item.minimum_stock,
                    cabinet_id=self._cabinets[item.cabinet],
                )
            )
            self._items[item.name] = (record.id, item)
            self._backdater.row("inventory_items", record.id, opened)

            # A new item starts at nothing — the app is firm about that,
            # because stock is meant to arrive through a document. What
            # was on the shelf the day the shop started using it arrives
            # the same way it would in real life: as a counted-in
            # adjustment, dated before the first purchase.
            if item.opening_stock:
                self._record_movement(
                    item_id=record.id,
                    movement_type=MovementType.ADJUSTMENT,
                    quantity_change=item.opening_stock,
                    when=opened,
                    reason="Opening stock count",
                )

    # ---------------- documents ----------------

    def _documents(self) -> None:
        """Purchases and sales together, oldest first.

        Interleaved rather than one kind after the other so that stock
        moves the way it really would: the previous and resulting counts
        recorded on each line are then the counts as of that date, not the
        counts after every purchase in the file had already been received.

        The order is load-bearing for **cost** as well as for stock. A
        sale records the average of what its item had been bought for *so
        far*, so splitting this back into two loops would price every
        seeded sale off the whole file's purchases and silently flatten
        every margin the reports show.
        """
        documents = chain(
            ((document, True) for document in self.dataset.purchases),
            ((document, False) for document in self.dataset.sales),
        )
        for document, buying in sorted(documents, key=lambda pair: -pair[0].days_ago):
            try:
                if buying:
                    self._purchase(document)
                else:
                    self._sale(document)
            except Exception as exc:  # noqa: BLE001 - re-raised, named
                raise RuntimeError(f"{document.reference}: {exc}") from exc

    def _purchase(self, document: DocumentSeed) -> None:
        record = self.container.create_purchase_use_case().execute(
            CreatePurchaseCommand(
                purchase_no=document.reference,
                supplier_id=self._party(self._suppliers, document.party),
                reference_no=document.reference_no,
                note=document.note,
                discount_amount=document.discount,
                items=[
                    PurchaseItemCommand(
                        item_type=ItemType.INVENTORY_ITEM,
                        inventory_item_id=self._items[line.item][0],
                        quantity=line.quantity,
                        unit_price=self._price(line, selling=False),
                    )
                    for line in document.lines
                ],
                payments=[
                    PurchasePaymentCommand(
                        amount=payment.amount,
                        paid_by_user_id=self._user_id,
                        payment_method_id=self._method(payment.method),
                    )
                    for payment in document.payments
                ],
            )
        )
        self._dated(backdating.PURCHASE, record.id, document)

    def _sale(self, document: DocumentSeed) -> None:
        record = self.container.create_sale_use_case().execute(
            CreateSaleCommand(
                invoice_no=document.reference,
                customer_id=self._party(self._customers, document.party),
                note=document.note,
                discount_amount=document.discount,
                items=[
                    SaleItemCommand(
                        item_type=ItemType.INVENTORY_ITEM,
                        inventory_item_id=self._items[line.item][0],
                        quantity=line.quantity,
                        unit_price=self._price(line, selling=True),
                    )
                    for line in document.lines
                ],
                payments=[
                    SalePaymentCommand(
                        amount=payment.amount,
                        received_by_user_id=self._user_id,
                        payment_method_id=self._method(payment.method),
                    )
                    for payment in document.payments
                ],
            )
        )
        self._dated(backdating.SALE, record.id, document)

    def _dated(self, tables, document_id: int, document: DocumentSeed) -> None:
        self._backdater.document(
            tables,
            document_id,
            self._moment(document.days_ago, _DOCUMENT_AT),
            [self._moment(payment.days_ago, _PAYMENT_AT) for payment in document.payments],
        )
        self._payments += len(document.payments)

    # ---------------- the rest ----------------

    def _expenses(self) -> None:
        for expense in self.dataset.expenses:
            record = self.container.create_expense_use_case().execute(
                CreateExpenseCommand(
                    expense_name=expense.name,
                    amount=expense.amount,
                    quantity=expense.quantity,
                    unit_price=expense.unit_price,
                    category_id=self._categories[expense.category],
                    remarks=expense.remarks,
                )
            )
            self._backdater.row(
                "expenses", record.id, self._moment(expense.days_ago, _EXPENSE_AT)
            )

    def _movements(self) -> None:
        for movement in self.dataset.movements:
            self._record_movement(
                item_id=self._items[movement.item][0],
                movement_type=MovementType(movement.movement_type),
                quantity_change=movement.quantity_change,
                when=self._moment(movement.days_ago, _MOVEMENT_AT),
                reason=movement.reason,
                note=movement.note,
            )

    def _audits(self) -> None:
        """Sign-in history, written the way signing in writes it.

        Nothing else produces any: a seeding run signs in once and
        deliberately leaves no trace of itself, so without this the
        history screen shows one row and its paging is never exercised.
        """
        record_audit = self.container.record_login_audit_use_case()
        for audit in self.dataset.audits:
            record = record_audit.execute(
                RecordLoginAuditCommand(
                    email=audit.email,
                    event_type=LoginEventType(audit.event_type),
                    user_id=self._user_id,
                    success=audit.success,
                    message=audit.message,
                )
            )
            self._backdater.row(
                "login_audits", record.id, self._moment(audit.days_ago, _SIGN_IN_AT)
            )

    def _record_movement(
        self,
        *,
        item_id: int,
        movement_type: MovementType,
        quantity_change: int,
        when: datetime,
        reason: str | None = None,
        note: str | None = None,
    ) -> None:
        record = self.container.record_inventory_movement_use_case().execute(
            InventoryMovementCommand(
                movement_type=movement_type,
                item_type=ItemType.INVENTORY_ITEM,
                inventory_item_id=item_id,
                quantity_change=quantity_change,
                reason=reason,
                note=note,
                created_by_user_id=self._user_id,
            )
        )
        self._backdater.row("inventory_movements", record.id, when, "occurred_at")
        self._movements_recorded += 1

    # ---------------- lookups ----------------

    def _party(self, known: dict[str, int], name: str | None) -> int | None:
        """None is a walk-in sale or a counter purchase — no party at all."""
        return None if name is None else known[name]

    def _method(self, name: str | None) -> int | None:
        """None is cash over the counter, which the app already reads as cash."""
        return None if name is None else self._methods[name]

    def _price(self, line: LineSeed, *, selling: bool) -> Decimal:
        if line.unit_price is not None:
            return line.unit_price
        _, item = self._items[line.item]
        return item.sale_price if selling else item.cost_price
