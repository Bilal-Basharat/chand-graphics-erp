# from pathlib import Path

# from app.config.settings import DATA_DIR
# from app.infrastructure.db.base import Base
# from app.infrastructure.db.database import engine
# from app.infrastructure.db.session import SessionLocal
# from app.infrastructure.db.models import (  # noqa: F401
#     CabinetModel,
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

import logging

from sqlalchemy import inspect

from app.config.settings import DATA_DIR
from app.infrastructure.db.base import Base
from app.infrastructure.db.database import engine

logger = logging.getLogger(__name__)

# Import models directly so SQLAlchemy registers them before create_all()
from app.infrastructure.db.models.cabinet_model import CabinetModel  # noqa: F401
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
from app.infrastructure.db.models.login_audit_model import LoginAuditModel  # noqa: F401
from app.infrastructure.db.upgrade import adopt_previous_installation, migrate

def init_db() -> None:
    """Make the database on disk match what this build expects.

    Order matters. An earlier installation's data is claimed first, so
    everything below runs against the customer's real file rather than a
    new empty one beside it. `create_all` then adds tables this build
    introduced — the only thing it can do to an existing database — and
    `migrate` changes the ones already there, which `create_all` never
    touches.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    adopt_previous_installation()
    Base.metadata.create_all(bind=engine)
    migrate(engine)
    _report_schema_drift()


def _report_schema_drift() -> None:
    """Say so, loudly and by name, if the file still differs from the models.

    Between them `create_all` and `migrate` should leave nothing behind.
    When they do not — a column added to a model with no step written for
    it — every query touching that table fails from the next startup on,
    and all the user is told is "something went wrong". Retrying never
    helps, and nothing on screen says which column is missing.

    Logged rather than raised: a column left over from an older build is
    harmless, and refusing to start over one would be worse than the
    problem it is reporting.
    """
    inspector = inspect(engine)
    live = set(inspector.get_table_names())

    for name, table in Base.metadata.tables.items():
        if name not in live:
            logger.error("Schema drift: table '%s' is missing", name)
            continue
        missing = {column.name for column in table.columns} - {
            column["name"] for column in inspector.get_columns(name)
        }
        if missing:
            logger.error(
                "Schema drift: '%s' has no %s. Every query against it will fail "
                "until a step in upgrade.py adds the column.",
                name,
                ", ".join(sorted(missing)),
            )