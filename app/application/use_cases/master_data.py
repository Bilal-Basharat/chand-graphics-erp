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
from app.domain.entities.card import Card
from app.domain.entities.company_settings import CompanySettings
from app.domain.entities.customer import Customer
from app.domain.entities.expense_category import ExpenseCategory
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.payment_method import PaymentMethod
from app.domain.entities.supplier import Supplier
from app.domain.uow import UnitOfWork


class CreateCabinetUseCase(UseCase[CreateCabinetCommand, Cabinet]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreateCabinetCommand) -> Cabinet:
        with self.uow as uow:
            cabinets = self.require(uow.cabinets, "cabinets")
            code = request.code.strip()

            if cabinets.get_by_code(code) is not None:
                raise DuplicateEntityError(f"Cabinet '{code}' already exists")

            cabinet = Cabinet(
                code=code,
                description=request.description,
                created_by_user_id=request.created_by_user_id,
            )
            return cabinets.add(cabinet)


class ListCabinetsUseCase(UseCase[int, list[Cabinet]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: int = 100) -> list[Cabinet]:
        with self.uow as uow:
            cabinets = self.require(uow.cabinets, "cabinets")
            return cabinets.list(limit=request)


class GetCabinetByCodeUseCase(UseCase[str, Cabinet | None]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: str) -> Cabinet | None:
        with self.uow as uow:
            cabinets = self.require(uow.cabinets, "cabinets")
            return cabinets.get_by_code(request.strip())


class CreateCardUseCase(UseCase[CreateCardCommand, Card]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreateCardCommand) -> Card:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            cabinets = self.require(uow.cabinets, "cabinets")

            card_number = request.card_number.strip()
            name = request.name.strip()

            if cards.get_by_card_number(card_number) is not None:
                raise DuplicateEntityError(f"Card '{card_number}' already exists")

            if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
                raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            card = Card(
                card_number=card_number,
                name=name,
                purchase_price=request.purchase_price,
                selling_price=request.selling_price,
                current_stock=request.current_stock,
                minimum_stock=request.minimum_stock,
                cabinet_id=request.cabinet_id,
                description=request.description,
                created_by_user_id=request.created_by_user_id,
            )
            return cards.add(card)


class ListCardsUseCase(UseCase[int, list[Card]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: int = 100) -> list[Card]:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            return cards.list(limit=request)


class GetCardByNumberUseCase(UseCase[str, Card | None]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: str) -> Card | None:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            return cards.get_by_card_number(request.strip())


class ListLowStockCardsUseCase(UseCase[int, list[Card]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: int = 100) -> list[Card]:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            return cards.list_low_stock(limit=request)


class CreateInventoryItemUseCase(UseCase[CreateInventoryItemCommand, InventoryItem]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreateInventoryItemCommand) -> InventoryItem:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")

            name = request.name.strip()
            if items.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Inventory item '{name}' already exists")

            item = InventoryItem(
                name=name,
                purchase_price=request.purchase_price,
                selling_price=request.selling_price,
                current_stock=request.current_stock,
                minimum_stock=request.minimum_stock,
                description=request.description,
                created_by_user_id=request.created_by_user_id,
            )
            return items.add(item)


class ListInventoryItemsUseCase(UseCase[int, list[InventoryItem]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: int = 100) -> list[InventoryItem]:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.list(limit=request)


class GetInventoryItemByNameUseCase(UseCase[str, InventoryItem | None]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: str) -> InventoryItem | None:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.get_by_name(request.strip())


class ListLowStockInventoryItemsUseCase(UseCase[int, list[InventoryItem]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: int = 100) -> list[InventoryItem]:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.list_low_stock(limit=request)


class CreateCustomerUseCase(UseCase[CreateCustomerCommand, Customer]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreateCustomerCommand) -> Customer:
        with self.uow as uow:
            customers = self.require(uow.customers, "customers")
            customer = Customer(
                name=request.name.strip(),
                phone=request.phone,
                address=request.address,
                notes=request.notes,
                created_by_user_id=request.created_by_user_id,
            )
            return customers.add(customer)


class SearchCustomersUseCase(UseCase[str, list[Customer]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: str) -> list[Customer]:
        with self.uow as uow:
            customers = self.require(uow.customers, "customers")
            return customers.search_by_name(request.strip())


class CreateSupplierUseCase(UseCase[CreateSupplierCommand, Supplier]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreateSupplierCommand) -> Supplier:
        with self.uow as uow:
            suppliers = self.require(uow.suppliers, "suppliers")
            supplier = Supplier(
                name=request.name.strip(),
                phone=request.phone,
                address=request.address,
                notes=request.notes,
                created_by_user_id=request.created_by_user_id,
            )
            return suppliers.add(supplier)


class SearchSuppliersUseCase(UseCase[str, list[Supplier]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: str) -> list[Supplier]:
        with self.uow as uow:
            suppliers = self.require(uow.suppliers, "suppliers")
            return suppliers.search_by_name(request.strip())


class CreatePaymentMethodUseCase(UseCase[CreatePaymentMethodCommand, PaymentMethod]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreatePaymentMethodCommand) -> PaymentMethod:
        with self.uow as uow:
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            name = request.name.strip()

            if payment_methods.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Payment method '{name}' already exists")

            payment_method = PaymentMethod(name=name)
            return payment_methods.add(payment_method)


class ListPaymentMethodsUseCase(UseCase[int, list[PaymentMethod]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: int = 100) -> list[PaymentMethod]:
        with self.uow as uow:
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            return payment_methods.list(limit=request)


class CreateExpenseCategoryUseCase(UseCase[CreateExpenseCategoryCommand, ExpenseCategory]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreateExpenseCategoryCommand) -> ExpenseCategory:
        with self.uow as uow:
            categories = self.require(uow.expense_categories, "expense_categories")
            name = request.name.strip()

            if categories.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Expense category '{name}' already exists")

            category = ExpenseCategory(
                name=name,
                description=request.description,
                created_by_user_id=request.created_by_user_id,
            )
            return categories.add(category)


class ListExpenseCategoriesUseCase(UseCase[int, list[ExpenseCategory]]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: int = 100) -> list[ExpenseCategory]:
        with self.uow as uow:
            categories = self.require(uow.expense_categories, "expense_categories")
            return categories.list(limit=request)


class CreateCompanySettingsUseCase(UseCase[CreateCompanySettingsCommand, CompanySettings]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: CreateCompanySettingsCommand) -> CompanySettings:
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
                created_by_user_id=request.created_by_user_id,
            )
            return settings_repo.add(settings)


class GetCompanySettingsUseCase(UseCase[None, CompanySettings | None]):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, request: None = None) -> CompanySettings | None:
        with self.uow as uow:
            settings_repo = self.require(uow.company_settings, "company_settings")
            return settings_repo.get_current()