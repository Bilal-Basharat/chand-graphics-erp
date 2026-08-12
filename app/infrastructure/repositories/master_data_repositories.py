from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.domain.entities.cabinet import Cabinet
from app.domain.entities.company_settings import CompanySettings
from app.domain.entities.customer import Customer
from app.domain.entities.expense_category import ExpenseCategory
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.payment_method import PaymentMethod
from app.domain.entities.supplier import Supplier
from app.domain.entities.user import User
from app.domain.repositories.cabinet_repository import CabinetRepository as CabinetRepositoryPort
from app.domain.repositories.company_settings_repository import (
    CompanySettingsRepository as CompanySettingsRepositoryPort,
)
from app.domain.repositories.customer_repository import CustomerRepository as CustomerRepositoryPort
from app.domain.repositories.expense_category_repository import (
    ExpenseCategoryRepository as ExpenseCategoryRepositoryPort,
)
from app.domain.repositories.inventory_item_repository import (
    InventoryItemRepository as InventoryItemRepositoryPort,
)
from app.domain.repositories.payment_method_repository import (
    PaymentMethodRepository as PaymentMethodRepositoryPort,
)
from app.domain.repositories.supplier_repository import SupplierRepository as SupplierRepositoryPort
from app.domain.repositories.user_repository import UserRepository as UserRepositoryPort
from app.infrastructure.db.models.cabinet_model import CabinetModel
from app.infrastructure.db.models.company_settings_model import CompanySettingsModel
from app.infrastructure.db.models.customer_model import CustomerModel
from app.infrastructure.db.models.expense_category_model import ExpenseCategoryModel
from app.infrastructure.db.models.inventory_item_model import InventoryItemModel
from app.infrastructure.db.models.payment_method_model import PaymentMethodModel
from app.infrastructure.db.models.supplier_model import SupplierModel
from app.infrastructure.db.models.user_model import UserModel
from app.infrastructure.mappers.cabinet_mapper import CabinetMapper
from app.infrastructure.mappers.company_settings_mapper import CompanySettingsMapper
from app.infrastructure.mappers.customer_mapper import CustomerMapper
from app.infrastructure.mappers.expense_category_mapper import ExpenseCategoryMapper
from app.infrastructure.mappers.inventory_item_mapper import InventoryItemMapper
from app.infrastructure.mappers.payment_method_mapper import PaymentMethodMapper
from app.infrastructure.mappers.supplier_mapper import SupplierMapper
from app.infrastructure.mappers.user_mapper import UserMapper
from app.infrastructure.repositories.base import SQLAlchemyRepository


############################################################
############### Inventory Items Repository #################
############################################################
class SqlAlchemyInventoryItemRepository(
    SQLAlchemyRepository[InventoryItem, InventoryItemModel],
    InventoryItemRepositoryPort,
):
    """
    Persistence for inventory master records.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, InventoryItemModel, InventoryItemMapper)

    def get_by_name(self, name: str) -> InventoryItem | None:
        return self.find_one_by("name", name)

    def names_by_id(self, item_ids: Collection[int]) -> dict[int, str]:
        """Item names for a set of items, keyed by id.

        For naming what a report grouped by, without loading the items.
        """
        ids = set(item_ids)
        if not ids:
            return {}
        stmt = select(InventoryItemModel.id, InventoryItemModel.name).where(
            InventoryItemModel.id.in_(ids)
        )
        return {row.id: row.name for row in self.session.execute(stmt)}

    def list_low_stock(self, limit: int = 100) -> list[InventoryItem]:
        stmt = (
            select(InventoryItemModel)
            .where(InventoryItemModel.current_stock <= InventoryItemModel.minimum_stock)
            .order_by(InventoryItemModel.name.asc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [InventoryItemMapper.to_entity(model) for model in models]

    def search_by_term(self, term: str, limit: int = 50) -> list[InventoryItem]:
        pattern = f"%{term.strip()}%"
        stmt = (
            select(InventoryItemModel)
            .where(
                or_(
                    InventoryItemModel.name.ilike(pattern),
                    InventoryItemModel.description.ilike(pattern),
                )
            )
            .order_by(InventoryItemModel.name.asc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [InventoryItemMapper.to_entity(model) for model in models]

    def clear_cabinet_id(self, cabinet_id: int) -> int:
        stmt = (
            update(InventoryItemModel)
            .where(InventoryItemModel.cabinet_id == cabinet_id)
            .values(cabinet_id=None)
        )
        return int(self.session.execute(stmt).rowcount)


############################################################
################### Cabinet Repository #####################
############################################################
class SqlAlchemyCabinetRepository(
    SQLAlchemyRepository[Cabinet, CabinetModel],
    CabinetRepositoryPort,
):
    """
    Persistence for cabinet master records.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, CabinetModel, CabinetMapper)

    def get_by_code(self, code: str) -> Cabinet | None:
        return self.find_one_by("code", code)


############################################################
################### Customer Repository ####################
############################################################
class SqlAlchemyCustomerRepository(
    SQLAlchemyRepository[Customer, CustomerModel],
    CustomerRepositoryPort,
):
    """
    Persistence for customer master records.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, CustomerModel, CustomerMapper)

    def search_by_name(self, term: str, limit: int = 50) -> list[Customer]:
        stmt = (
            select(CustomerModel)
            .where(CustomerModel.name.ilike(f"%{term}%"))
            .order_by(CustomerModel.name.asc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [CustomerMapper.to_entity(model) for model in models]


############################################################
################### Supplier Repository ####################
############################################################
class SqlAlchemySupplierRepository(
    SQLAlchemyRepository[Supplier, SupplierModel],
    SupplierRepositoryPort,
):
    """
    Persistence for supplier master records.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, SupplierModel, SupplierMapper)

    def search_by_name(self, term: str, limit: int = 50) -> list[Supplier]:
        stmt = (
            select(SupplierModel)
            .where(SupplierModel.name.ilike(f"%{term}%"))
            .order_by(SupplierModel.name.asc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [SupplierMapper.to_entity(model) for model in models]


############################################################
################ Payment Method Repository #################
############################################################
class SqlAlchemyPaymentMethodRepository(
    SQLAlchemyRepository[PaymentMethod, PaymentMethodModel],
    PaymentMethodRepositoryPort,
):
    """
    Persistence for payment method master records.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, PaymentMethodModel, PaymentMethodMapper)

    def get_by_name(self, name: str) -> PaymentMethod | None:
        return self.find_one_by("name", name)


############################################################
##################### User Repository ######################
############################################################
class SqlAlchemyUserRepository(
    SQLAlchemyRepository[User, UserModel],
    UserRepositoryPort,
):
    """
    Persistence for application users.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, UserModel, UserMapper)

    def get_by_email(self, email: str) -> User | None:
        return self.find_one_by("email", email)



############################################################
############### Expense Category Repository ################
############################################################
class SqlAlchemyExpenseCategoryRepository(
    SQLAlchemyRepository[ExpenseCategory, ExpenseCategoryModel],
    ExpenseCategoryRepositoryPort,
):
    """
    Persistence for expense categories.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, ExpenseCategoryModel, ExpenseCategoryMapper)

    def get_by_name(self, name: str) -> ExpenseCategory | None:
        return self.find_one_by("name", name)


############################################################
############### Company Settings Repository ################
############################################################
class SqlAlchemyCompanySettingsRepository(
    SQLAlchemyRepository[CompanySettings, CompanySettingsModel],
    CompanySettingsRepositoryPort,
):
    """
    Persistence for company settings.

    Typically one settings row per database.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, CompanySettingsModel, CompanySettingsMapper)

    def get_current(self) -> CompanySettings | None:
        stmt = select(CompanySettingsModel).order_by(CompanySettingsModel.id.asc()).limit(1)
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else CompanySettingsMapper.to_entity(model)