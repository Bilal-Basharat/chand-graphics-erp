from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.base import Base
from app.infrastructure.uow import SqlAlchemyUnitOfWork


def _register_models() -> None:
    """
    Import all SQLAlchemy models so their tables are registered on Base.metadata.
    """
    from app.infrastructure.db.models.cabinet_model import CabinetModel  # noqa: F401
    from app.infrastructure.db.models.card_model import CardModel  # noqa: F401
    from app.infrastructure.db.models.company_settings_model import CompanySettingsModel  # noqa: F401
    from app.infrastructure.db.models.customer_model import CustomerModel  # noqa: F401
    from app.infrastructure.db.models.expense_category_model import ExpenseCategoryModel  # noqa: F401
    from app.infrastructure.db.models.expense_model import ExpenseModel  # noqa: F401
    from app.infrastructure.db.models.inventory_item_model import InventoryItemModel  # noqa: F401
    from app.infrastructure.db.models.inventory_movement_model import InventoryMovementModel  # noqa: F401
    from app.infrastructure.db.models.payment_method_model import PaymentMethodModel  # noqa: F401
    from app.infrastructure.db.models.purchase_item_model import PurchaseItemModel  # noqa: F401
    from app.infrastructure.db.models.purchase_model import PurchaseModel  # noqa: F401
    from app.infrastructure.db.models.purchase_payment_model import PurchasePaymentModel  # noqa: F401
    from app.infrastructure.db.models.sale_item_model import SaleItemModel  # noqa: F401
    from app.infrastructure.db.models.sale_model import SaleModel  # noqa: F401
    from app.infrastructure.db.models.sale_payment_model import SalePaymentModel  # noqa: F401
    from app.infrastructure.db.models.supplier_model import SupplierModel  # noqa: F401
    from app.infrastructure.db.models.user_model import UserModel  # noqa: F401


@pytest.fixture()
def db_engine(tmp_path: Path):
    """
    Creates a fresh SQLite database for each test function.
    """
    _register_models()

    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def session_factory(db_engine):
    """
    Session factory bound to the test database.
    """
    return sessionmaker(
        bind=db_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@pytest.fixture()
def uow(session_factory):
    """
    UnitOfWork bound to the isolated test database.
    """
    return SqlAlchemyUnitOfWork(session_factory=session_factory)


@pytest.fixture()
def admin_session(uow):
    """
    A signed-in admin CurrentUserSession for use cases that require authentication/authorization.
    """
    from app.application.auth.session import CurrentUserSession
    from app.domain.entities.user import User

    with uow as u:
        user = u.users.add(
            User(email="admin@test.local", password_hash="x", full_name="Test Admin", role="admin")
        )

    session = CurrentUserSession()
    session.set_user(user)
    return session