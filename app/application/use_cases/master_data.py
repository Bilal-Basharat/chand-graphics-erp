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
)
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.base import UseCase
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
from app.application.use_cases.authorized_base import AuthorizedUseCase

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


class SearchCustomersUseCase(AuthenticatedUseCase[str, list[Customer]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> list[Customer]:
        with self.uow as uow:
            customers = self.require(uow.customers, "customers")
            return customers.search_by_name(request.strip())


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


class SearchSuppliersUseCase(AuthenticatedUseCase[str, list[Supplier]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> list[Supplier]:
        with self.uow as uow:
            suppliers = self.require(uow.suppliers, "suppliers")
            return suppliers.search_by_name(request.strip())


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


class GetCompanySettingsUseCase(AuthenticatedUseCase[None, CompanySettings | None]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: None = None) -> CompanySettings | None:
        with self.uow as uow:
            settings_repo = self.require(uow.company_settings, "company_settings")
            return settings_repo.get_current()