from pathlib import Path

from app.config.settings import DATA_DIR
from app.infrastructure.db.base import Base
from app.infrastructure.db.database import engine
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import (  # noqa: F401
    CabinetModel,
    CardModel,
    CustomerModel,
    ExpenseModel,
    InventoryItemModel,
    PaymentMethodModel,
    PurchaseModel,
    PurchaseItemModel,
    PurchasePaymentModel,
    SaleModel,
    SaleItemModel,
    SalePaymentModel,
    SupplierModel,
    UserModel,
)

def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)