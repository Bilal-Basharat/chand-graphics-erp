# from pathlib import Path

# from app.config.settings import DATA_DIR
# from app.infrastructure.db.base import Base
# from app.infrastructure.db.database import engine
# from app.infrastructure.db.session import SessionLocal
# from app.infrastructure.db.models import (  # noqa: F401
#     CabinetModel,
#     CardModel,
#     CustomerModel,
#     ExpenseModel,
#     InventoryItemModel,
#     PaymentMethodModel,
#     PurchaseModel,
#     PurchaseItemModel,
#     PurchasePaymentModel,
#     SaleModel,
#     SaleItemModel,
#     SalePaymentModel,
#     SupplierModel,
#     UserModel,
# )

# def init_db() -> None:
#     DATA_DIR.mkdir(parents=True, exist_ok=True)
#     Base.metadata.create_all(bind=engine)

from app.config.settings import DATA_DIR
from app.infrastructure.db.base import Base
from app.infrastructure.db.database import engine

# Import models directly so SQLAlchemy registers them before create_all()
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


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)