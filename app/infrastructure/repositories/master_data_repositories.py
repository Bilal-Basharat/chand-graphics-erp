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
from app.domain.enums.stock_filter import StockFilter
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
from app.infrastructure.repositories.paging import contains, matching


class _TextSearched:
    """A list that is narrowed by typing and ordered by a whitelist.

    Five of the master-data lists are exactly that and differ only in
    which columns the term is looked for in and what may be sorted by, so
    they declare those two things and share the rest. Each still names its
    own `page_*`/`count_*` pair — a call site reads better saying what it
    is asking for — but the statement behind both is built once, because a
    condition applied to the page and forgotten in the count is a list
    that disagrees with its own page numbers.
    """

    _SORTABLE: dict
    _DEFAULT_SORT: str
    _SEARCHED: tuple

    def _filtered(self, search: str):
        stmt = select(self.model_class)
        if search:
            stmt = stmt.where(matching(contains(search), *self._SEARCHED))
        return stmt

    def _page(self, search: str, sort_field: str | None, sort_desc: bool, limit: int, offset: int):
        return self.page_of(
            self._filtered(search),
            sortable=self._SORTABLE,
            default_sort=self._DEFAULT_SORT,
            sort_field=sort_field,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )


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

    _SORTABLE = {
        "name": InventoryItemModel.name,
        "stock": InventoryItemModel.current_stock,
        "minimum": InventoryItemModel.minimum_stock,
        "created": InventoryItemModel.created_at,
    }
    """What the catalogue may be ordered by, as the screen names it. A
    column that is not here cannot be sorted on, and the heading for it
    says so by carrying no mark."""

    def get_by_name(self, name: str) -> InventoryItem | None:
        return self.find_one_by("name", name)

    def _filtered_items(self, search: str, stock: str | None):
        """The conditions both the page and its count are subject to.

        Written once: a filter applied to the rows and forgotten in the
        count is a list that disagrees with its own page numbers.
        """
        stmt = select(InventoryItemModel)
        if search:
            stmt = stmt.where(
                matching(
                    contains(search),
                    InventoryItemModel.name,
                    InventoryItemModel.description,
                )
            )
        if stock == StockFilter.LOW:
            stmt = stmt.where(InventoryItemModel.current_stock <= InventoryItemModel.minimum_stock)
        elif stock == StockFilter.OUT:
            stmt = stmt.where(InventoryItemModel.current_stock <= 0)
        elif stock == StockFilter.IN:
            stmt = stmt.where(InventoryItemModel.current_stock > InventoryItemModel.minimum_stock)
        return stmt

    def page_items(
        self,
        *,
        search: str = "",
        stock: str | None = None,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InventoryItem]:
        return self.page_of(
            self._filtered_items(search, stock),
            sortable=self._SORTABLE,
            default_sort="name",
            sort_field=sort_field,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

    def count_items(self, *, search: str = "", stock: str | None = None) -> int:
        return self.count_of(self._filtered_items(search, stock))

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
    _TextSearched,
    SQLAlchemyRepository[Cabinet, CabinetModel],
    CabinetRepositoryPort,
):
    """
    Persistence for cabinet master records.
    """

    _SORTABLE = {"code": CabinetModel.code, "created": CabinetModel.created_at}
    _DEFAULT_SORT = "code"
    _SEARCHED = (CabinetModel.code, CabinetModel.description)

    def __init__(self, session: Session) -> None:
        super().__init__(session, CabinetModel, CabinetMapper)

    def get_by_code(self, code: str) -> Cabinet | None:
        return self.find_one_by("code", code)

    def page_cabinets(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Cabinet]:
        return self._page(search, sort_field, sort_desc, limit, offset)

    def count_cabinets(self, *, search: str = "") -> int:
        return self.count_of(self._filtered(search))

    def names_by_id(self, cabinet_ids: Collection[int]) -> dict[int, str]:
        ids = set(cabinet_ids)
        if not ids:
            return {}
        stmt = select(CabinetModel.id, CabinetModel.code).where(CabinetModel.id.in_(ids))
        return {row.id: row.code for row in self.session.execute(stmt)}


############################################################
################### Customer Repository ####################
############################################################
class SqlAlchemyCustomerRepository(
    _TextSearched,
    SQLAlchemyRepository[Customer, CustomerModel],
    CustomerRepositoryPort,
):
    """
    Persistence for customer master records.
    """

    _SORTABLE = {
        "name": CustomerModel.name,
        "phone": CustomerModel.phone,
        "balance": CustomerModel.opening_balance,
        "created": CustomerModel.created_at,
    }
    _DEFAULT_SORT = "name"
    _SEARCHED = (CustomerModel.name, CustomerModel.phone)
    """By number as well as by name: a shop that knows a customer by the
    number they ring from has no other way to find them."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, CustomerModel, CustomerMapper)

    def page_customers(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Customer]:
        return self._page(search, sort_field, sort_desc, limit, offset)

    def count_customers(self, *, search: str = "") -> int:
        return self.count_of(self._filtered(search))

    def names_by_id(self, customer_ids: Collection[int]) -> dict[int, str]:
        ids = set(customer_ids)
        if not ids:
            return {}
        stmt = select(CustomerModel.id, CustomerModel.name).where(CustomerModel.id.in_(ids))
        return {row.id: row.name for row in self.session.execute(stmt)}


############################################################
################### Supplier Repository ####################
############################################################
class SqlAlchemySupplierRepository(
    _TextSearched,
    SQLAlchemyRepository[Supplier, SupplierModel],
    SupplierRepositoryPort,
):
    """
    Persistence for supplier master records.
    """

    _SORTABLE = {
        "name": SupplierModel.name,
        "phone": SupplierModel.phone,
        "balance": SupplierModel.opening_balance,
        "created": SupplierModel.created_at,
    }
    _DEFAULT_SORT = "name"
    _SEARCHED = (SupplierModel.name, SupplierModel.phone)

    def __init__(self, session: Session) -> None:
        super().__init__(session, SupplierModel, SupplierMapper)

    def page_suppliers(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Supplier]:
        return self._page(search, sort_field, sort_desc, limit, offset)

    def count_suppliers(self, *, search: str = "") -> int:
        return self.count_of(self._filtered(search))

    def names_by_id(self, supplier_ids: Collection[int]) -> dict[int, str]:
        ids = set(supplier_ids)
        if not ids:
            return {}
        stmt = select(SupplierModel.id, SupplierModel.name).where(SupplierModel.id.in_(ids))
        return {row.id: row.name for row in self.session.execute(stmt)}



############################################################
################ Payment Method Repository #################
############################################################
class SqlAlchemyPaymentMethodRepository(
    _TextSearched,
    SQLAlchemyRepository[PaymentMethod, PaymentMethodModel],
    PaymentMethodRepositoryPort,
):
    """
    Persistence for payment method master records.
    """

    _SORTABLE = {"name": PaymentMethodModel.name, "created": PaymentMethodModel.created_at}
    _DEFAULT_SORT = "name"
    _SEARCHED = (PaymentMethodModel.name,)

    def __init__(self, session: Session) -> None:
        super().__init__(session, PaymentMethodModel, PaymentMethodMapper)

    def get_by_name(self, name: str) -> PaymentMethod | None:
        return self.find_one_by("name", name)

    def page_payment_methods(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PaymentMethod]:
        return self._page(search, sort_field, sort_desc, limit, offset)

    def count_payment_methods(self, *, search: str = "") -> int:
        return self.count_of(self._filtered(search))

    def names_by_id(self, method_ids: Collection[int]) -> dict[int, str]:
        ids = set(method_ids)
        if not ids:
            return {}
        stmt = select(PaymentMethodModel.id, PaymentMethodModel.name).where(
            PaymentMethodModel.id.in_(ids)
        )
        return {row.id: row.name for row in self.session.execute(stmt)}


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
    _TextSearched,
    SQLAlchemyRepository[ExpenseCategory, ExpenseCategoryModel],
    ExpenseCategoryRepositoryPort,
):
    """
    Persistence for expense categories.
    """

    _SORTABLE = {
        "name": ExpenseCategoryModel.name,
        "created": ExpenseCategoryModel.created_at,
    }
    _DEFAULT_SORT = "name"
    _SEARCHED = (ExpenseCategoryModel.name, ExpenseCategoryModel.description)

    def __init__(self, session: Session) -> None:
        super().__init__(session, ExpenseCategoryModel, ExpenseCategoryMapper)

    def get_by_name(self, name: str) -> ExpenseCategory | None:
        return self.find_one_by("name", name)

    def page_expense_categories(
        self,
        *,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExpenseCategory]:
        return self._page(search, sort_field, sort_desc, limit, offset)

    def count_expense_categories(self, *, search: str = "") -> int:
        return self.count_of(self._filtered(search))

    def names_by_id(self, category_ids: Collection[int]) -> dict[int, str]:
        ids = set(category_ids)
        if not ids:
            return {}
        stmt = select(ExpenseCategoryModel.id, ExpenseCategoryModel.name).where(
            ExpenseCategoryModel.id.in_(ids)
        )
        return {row.id: row.name for row in self.session.execute(stmt)}


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