from __future__ import annotations

from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateCardCommand,
    CreateCompanySettingsCommand,
    CreateCustomerCommand,
    CreateExpenseCategoryCommand,
    CreateInventoryItemCommand,
    CreatePaymentMethodCommand,
    CreateSupplierCommand,
    DateRangeQuery,
    UpdateCabinetCommand,
    UpdateCompanySettingsCommand,
    UpdateCustomerCommand,
    UpdateExpenseCategoryCommand,
    UpdatePaymentMethodCommand,
    UpdateSupplierCommand,
)
from app.application.dto.queries import SearchQuery
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.base import UseCase
from app.application.use_cases.deletion_guard import ensure_not_in_use
from app.domain.entities.cabinet import Cabinet
from app.domain.entities.company_settings import CompanySettings
from app.domain.entities.customer import Customer
from app.domain.entities.expense_category import ExpenseCategory
from app.domain.entities.payment_method import PaymentMethod
from app.domain.entities.supplier import Supplier
from app.domain.uow import UnitOfWork

from app.application.auth.session import CurrentUserSession
from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import (
    AuthorizedUnitOfWorkUseCase,
    AuthorizedUseCase,
)

############################################################
################### Cabinet Use Cases ######################
############################################################
class CreateCabinetUseCase(AuthorizedUseCase[CreateCabinetCommand, Cabinet]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreateCabinetCommand) -> Cabinet:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()
        
        with self.uow as uow:
            cabinets = self.require(uow.cabinets, "cabinets")
            code = request.code.strip()

            if cabinets.get_by_code(code) is not None:
                raise DuplicateEntityError(f"Cabinet '{code}' already exists")

            cabinet = Cabinet(
                code=code,
                description=request.description,
                created_by_user_id=current_user_id,
            )
            return cabinets.add(cabinet)


class ListCabinetsUseCase(AuthenticatedUseCase[int, list[Cabinet]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[Cabinet]:
        with self.uow as uow:
            cabinets = self.require(uow.cabinets, "cabinets")
            return cabinets.list(limit=request)


class GetCabinetByCodeUseCase(AuthenticatedUseCase[str, Cabinet | None]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> Cabinet | None:
        with self.uow as uow:
            cabinets = self.require(uow.cabinets, "cabinets")
            return cabinets.get_by_code(request.strip())


class UpdateCabinetUseCase(AuthorizedUnitOfWorkUseCase[UpdateCabinetCommand, Cabinet]):
    def execute(self, request: UpdateCabinetCommand) -> Cabinet:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            cabinets = self.require(uow.cabinets, "cabinets")

            cabinet = cabinets.get_by_id(request.id)
            if cabinet is None:
                raise NotFoundError(f"Cabinet id={request.id} not found")

            code = request.code.strip()
            clash = cabinets.get_by_code(code)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Cabinet '{code}' already exists")

            cabinet.code = code
            cabinet.description = request.description
            cabinet.updated_by_user_id = current_user_id

            return cabinets.update(cabinet)


class DeleteCabinetUseCase(AuthorizedUnitOfWorkUseCase[int, int]):
    """
    Remove a cabinet, unfiling whatever was in it.

    A cabinet is where a card is kept, not what it is, so the cards
    themselves survive — they simply stop naming a cabinet that no longer
    exists. Returns how many were unfiled.
    """

    def execute(self, request: int) -> int:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            cabinets = self.require(uow.cabinets, "cabinets")
            cards = self.require(uow.cards, "cards")

            cabinet = cabinets.get_by_id(request)
            if cabinet is None:
                raise NotFoundError(f"Cabinet id={request} not found")

            unfiled = cards.clear_cabinet_id(request)
            cabinets.delete(request)
            return unfiled


############################################################
################### Customer Use Cases ######################
############################################################
class CreateCustomerUseCase(AuthorizedUseCase[CreateCustomerCommand, Customer]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreateCustomerCommand) -> Customer:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            customers = self.require(uow.customers, "customers")

            customer = Customer(
                name=request.name.strip(),
                phone=request.phone,
                address=request.address,
                notes=request.notes,
                created_by_user_id=current_user_id,
            )
            return customers.add(customer)


class SearchCustomersUseCase(AuthenticatedUseCase[SearchQuery, list[Customer]]):
    """An empty term lists every customer, up to the query's limit."""

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: SearchQuery) -> list[Customer]:
        with self.uow as uow:
            customers = self.require(uow.customers, "customers")
            return customers.search_by_name(request.term.strip(), request.limit)


class UpdateCustomerUseCase(AuthorizedUseCase[UpdateCustomerCommand, Customer]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: UpdateCustomerCommand) -> Customer:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            customers = self.require(uow.customers, "customers")

            customer = customers.get_by_id(request.id)
            if customer is None:
                raise NotFoundError(f"Customer id={request.id} not found")

            customer.name = request.name.strip()
            customer.phone = request.phone
            customer.address = request.address
            customer.notes = request.notes
            customer.updated_by_user_id = current_user_id

            return customers.update(customer)


class DeleteCustomerUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """
    Remove a customer, unless sales are recorded against them.

    A sale is a financial record, and the party it was made to is part of
    what it records. Deleting the customer cannot leave that intact, so it
    is refused while any sale exists rather than quietly taking the sales
    down too — the caller is told how many are in the way.
    """

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            customers = self.require(uow.customers, "customers")
            sales = self.require(uow.sales, "sales")

            customer = customers.get_by_id(request)
            if customer is None:
                raise NotFoundError(f"Customer id={request} not found")

            ensure_not_in_use(customer.name, {"sale": sales.count_by_customer(request)})

            customers.delete(request)


############################################################
################### Supplier Use Cases ######################
############################################################
class CreateSupplierUseCase(AuthorizedUseCase[CreateSupplierCommand, Supplier]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreateSupplierCommand) -> Supplier:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            suppliers = self.require(uow.suppliers, "suppliers")

            supplier = Supplier(
                name=request.name.strip(),
                phone=request.phone,
                address=request.address,
                notes=request.notes,
                created_by_user_id=current_user_id,
            )
            return suppliers.add(supplier)


class SearchSuppliersUseCase(AuthenticatedUseCase[SearchQuery, list[Supplier]]):
    """An empty term lists every supplier, up to the query's limit."""

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: SearchQuery) -> list[Supplier]:
        with self.uow as uow:
            suppliers = self.require(uow.suppliers, "suppliers")
            return suppliers.search_by_name(request.term.strip(), request.limit)


class UpdateSupplierUseCase(AuthorizedUseCase[UpdateSupplierCommand, Supplier]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: UpdateSupplierCommand) -> Supplier:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            suppliers = self.require(uow.suppliers, "suppliers")

            supplier = suppliers.get_by_id(request.id)
            if supplier is None:
                raise NotFoundError(f"Supplier id={request.id} not found")

            supplier.name = request.name.strip()
            supplier.phone = request.phone
            supplier.address = request.address
            supplier.notes = request.notes
            supplier.updated_by_user_id = current_user_id

            return suppliers.update(supplier)


class DeleteSupplierUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """Remove a supplier, unless purchases are recorded against them — see
    `DeleteCustomerUseCase` for why that is refused rather than cascaded."""

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            suppliers = self.require(uow.suppliers, "suppliers")
            purchases = self.require(uow.purchases, "purchases")

            supplier = suppliers.get_by_id(request)
            if supplier is None:
                raise NotFoundError(f"Supplier id={request} not found")

            ensure_not_in_use(supplier.name, {"purchase": purchases.count_by_supplier(request)})

            suppliers.delete(request)


############################################################
################ Payment Method Use Cases ##################
############################################################
class CreatePaymentMethodUseCase(AuthorizedUseCase[CreatePaymentMethodCommand, PaymentMethod]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreatePaymentMethodCommand) -> PaymentMethod:
        self.require_permission(Permission.MANAGE_SETTINGS)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            name = request.name.strip()

            if payment_methods.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Payment method '{name}' already exists")

            payment_method = PaymentMethod(name=name, created_by_user_id=current_user_id)
            return payment_methods.add(payment_method)


class ListPaymentMethodsUseCase(AuthenticatedUseCase[int, list[PaymentMethod]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[PaymentMethod]:
        with self.uow as uow:
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            return payment_methods.list(limit=request)


class UpdatePaymentMethodUseCase(AuthorizedUnitOfWorkUseCase[UpdatePaymentMethodCommand, PaymentMethod]):
    def execute(self, request: UpdatePaymentMethodCommand) -> PaymentMethod:
        self.require_permission(Permission.MANAGE_SETTINGS)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            payment_methods = self.require(uow.payment_methods, "payment_methods")

            method = payment_methods.get_by_id(request.id)
            if method is None:
                raise NotFoundError(f"Payment method id={request.id} not found")

            name = request.name.strip()
            clash = payment_methods.get_by_name(name)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Payment method '{name}' already exists")

            method.name = name
            method.updated_by_user_id = current_user_id

            return payment_methods.update(method)


class DeletePaymentMethodUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """Remove a payment method, unless money has been recorded through it.

    Every payment names the method it came through; deleting the method
    would leave those payments unable to say how they were settled.
    """

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_SETTINGS)

        with self.uow as uow:
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            sales = self.require(uow.sales, "sales")
            purchases = self.require(uow.purchases, "purchases")

            method = payment_methods.get_by_id(request)
            if method is None:
                raise NotFoundError(f"Payment method id={request} not found")

            ensure_not_in_use(
                method.name,
                {
                    "sale payment": sales.count_by_payment_method(request),
                    "purchase payment": purchases.count_by_payment_method(request),
                },
            )

            payment_methods.delete(request)


############################################################
################### Expense Use Cases ######################
############################################################
class CreateExpenseCategoryUseCase(AuthorizedUseCase[CreateExpenseCategoryCommand, ExpenseCategory]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreateExpenseCategoryCommand) -> ExpenseCategory:
        self.require_permission(Permission.MANAGE_EXPENSES)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            categories = self.require(uow.expense_categories, "expense_categories")
            name = request.name.strip()


            if categories.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Expense category '{name}' already exists")

            category = ExpenseCategory(
                name=name,
                description=request.description,
                created_by_user_id=current_user_id
            )
            return categories.add(category)


class ListExpenseCategoriesUseCase(AuthenticatedUseCase[int, list[ExpenseCategory]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[ExpenseCategory]:
        with self.uow as uow:
            categories = self.require(uow.expense_categories, "expense_categories")
            return categories.list(limit=request)


class UpdateExpenseCategoryUseCase(
    AuthorizedUnitOfWorkUseCase[UpdateExpenseCategoryCommand, ExpenseCategory]
):
    def execute(self, request: UpdateExpenseCategoryCommand) -> ExpenseCategory:
        self.require_permission(Permission.MANAGE_EXPENSES)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            categories = self.require(uow.expense_categories, "expense_categories")

            category = categories.get_by_id(request.id)
            if category is None:
                raise NotFoundError(f"Expense category id={request.id} not found")

            name = request.name.strip()
            clash = categories.get_by_name(name)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Expense category '{name}' already exists")

            category.name = name
            category.description = request.description
            category.updated_by_user_id = current_user_id

            return categories.update(category)


class DeleteExpenseCategoryUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """Remove a category, unless expenses are booked to it — deleting it
    would leave that spending grouped under nothing, which is exactly what
    the category exists to prevent."""

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_EXPENSES)

        with self.uow as uow:
            categories = self.require(uow.expense_categories, "expense_categories")
            expenses = self.require(uow.expenses, "expenses")

            category = categories.get_by_id(request)
            if category is None:
                raise NotFoundError(f"Expense category id={request} not found")

            ensure_not_in_use(category.name, {"expense": expenses.count_by_category(request)})

            categories.delete(request)


############################################################
############### Company Settings Use Cases #################
############################################################
class CreateCompanySettingsUseCase(AuthorizedUseCase[CreateCompanySettingsCommand, CompanySettings]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreateCompanySettingsCommand) -> CompanySettings:
        self.require_permission(Permission.MANAGE_SETTINGS)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            settings_repo = self.require(uow.company_settings, "company_settings")


            if settings_repo.get_current() is not None:
                raise DuplicateEntityError("Company settings already exist for this database")

            settings = CompanySettings(
                company_name=request.company_name.strip(),
                phone=request.phone,
                email=request.email,
                address=request.address,
                currency=request.currency,
                logo_path=request.logo_path,
                invoice_footer=request.invoice_footer,
                created_by_user_id=current_user_id,
            )
            return settings_repo.add(settings)


class UpdateCompanySettingsUseCase(AuthorizedUseCase[UpdateCompanySettingsCommand, CompanySettings]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: UpdateCompanySettingsCommand) -> CompanySettings:
        self.require_permission(Permission.MANAGE_SETTINGS)

        with self.uow as uow:
            settings_repo = self.require(uow.company_settings, "company_settings")

            existing = settings_repo.get_current()
            if existing is None or existing.id != request.id:
                raise NotFoundError(f"Company settings id={request.id} not found")

            existing.company_name = request.company_name.strip()
            existing.phone = request.phone
            existing.email = request.email
            existing.address = request.address
            existing.currency = request.currency
            existing.logo_path = request.logo_path
            existing.invoice_footer = request.invoice_footer

            return settings_repo.update(existing)


class GetCompanySettingsUseCase(AuthenticatedUseCase[None, CompanySettings | None]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: None = None) -> CompanySettings | None:
        with self.uow as uow:
            settings_repo = self.require(uow.company_settings, "company_settings")
            return settings_repo.get_current()