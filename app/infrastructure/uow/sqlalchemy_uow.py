from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.uow import UnitOfWork
from app.infrastructure.db.session import SessionLocal

from app.infrastructure.repositories.master_data_repositories import (
    SqlAlchemyCabinetRepository,
    SqlAlchemyCardRepository,
    SqlAlchemyCompanySettingsRepository,
    SqlAlchemyCustomerRepository,
    SqlAlchemyExpenseCategoryRepository,
    SqlAlchemyInventoryItemRepository,
    SqlAlchemyPaymentMethodRepository,
    SqlAlchemySupplierRepository,
    SqlAlchemyUserRepository,
)

from app.infrastructure.repositories.transaction_repositories import (
    SqlAlchemyExpenseRepository,
    SqlAlchemyInventoryMovementRepository,
    SqlAlchemyPurchasePaymentRepository,
    SqlAlchemyPurchaseRepository,
    SqlAlchemySalePaymentRepository,
    SqlAlchemySaleRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """
    SQLAlchemy implementation of the Unit of Work pattern.

    One instance represents one database transaction.
    """

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory or SessionLocal
        self.session: Session | None = None

        self.cards: SqlAlchemyCardRepository | None = None
        self.inventory_items: SqlAlchemyInventoryItemRepository | None = None
        self.cabinets: SqlAlchemyCabinetRepository | None = None
        self.customers: SqlAlchemyCustomerRepository | None = None
        self.suppliers: SqlAlchemySupplierRepository | None = None
        self.users: SqlAlchemyUserRepository | None = None
        self.payment_methods: SqlAlchemyPaymentMethodRepository | None = None
        self.expense_categories: SqlAlchemyExpenseCategoryRepository | None = None
        self.company_settings: SqlAlchemyCompanySettingsRepository | None = None

        self.purchases: SqlAlchemyPurchaseRepository | None = None
        self.purchase_payments: SqlAlchemyPurchasePaymentRepository | None = None
        self.sales: SqlAlchemySaleRepository | None = None
        self.sale_payments: SqlAlchemySalePaymentRepository | None = None
        self.expenses: SqlAlchemyExpenseRepository | None = None
        self.inventory_movements: SqlAlchemyInventoryMovementRepository | None = None

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self._session_factory()
        self._initialize_repositories()
        return self

    def _initialize_repositories(self) -> None:
        """
        Create repository instances after the session is available.
        """
        if self.session is None:
            raise RuntimeError("UnitOfWork session is not initialized")

        self.cards = SqlAlchemyCardRepository(self.session)
        self.inventory_items = SqlAlchemyInventoryItemRepository(self.session)
        self.cabinets = SqlAlchemyCabinetRepository(self.session)
        self.customers = SqlAlchemyCustomerRepository(self.session)
        self.suppliers = SqlAlchemySupplierRepository(self.session)
        self.users = SqlAlchemyUserRepository(self.session)
        self.payment_methods = SqlAlchemyPaymentMethodRepository(self.session)
        self.expense_categories = SqlAlchemyExpenseCategoryRepository(self.session)
        self.company_settings = SqlAlchemyCompanySettingsRepository(self.session)

        self.purchases = SqlAlchemyPurchaseRepository(self.session)
        self.purchase_payments = SqlAlchemyPurchasePaymentRepository(self.session)
        self.sales = SqlAlchemySaleRepository(self.session)
        self.sale_payments = SqlAlchemySalePaymentRepository(self.session)
        self.expenses = SqlAlchemyExpenseRepository(self.session)
        self.inventory_movements = SqlAlchemyInventoryMovementRepository(self.session)

    def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork has no active session")
        self.session.commit()

    def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork has no active session")
        self.session.rollback()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.session is None:
            return

        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.session.close()
            self.session = None