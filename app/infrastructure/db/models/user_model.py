from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class UserModel(Base, AuditMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="operator",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    #############################################################
    #################### relationship methods ###################
    #############################################################

    cabinets = relationship(
        "CabinetModel",
        back_populates="created_by_user",
        foreign_keys="CabinetModel.created_by_user_id",
    )
    
    cards = relationship(
        "CardModel",
        back_populates="created_by_user",
        foreign_keys="CardModel.created_by_user_id",
    )

    inventory_items = relationship(
        "InventoryItemModel",
        back_populates="created_by_user",
        foreign_keys="InventoryItemModel.created_by_user_id",
    )
    sales = relationship(
        "SaleModel",
        back_populates="created_by_user",
        foreign_keys="SaleModel.created_by_user_id",
    )
    purchases = relationship(
        "PurchaseModel",
        back_populates="created_by_user",
        foreign_keys="PurchaseModel.created_by_user_id",
    )
    expenses = relationship(
        "ExpenseModel",
        back_populates="created_by_user",
        foreign_keys="ExpenseModel.created_by_user_id",
    )
    expense_categories = relationship(
        "ExpenseCategoryModel",
        back_populates="created_by_user",
        foreign_keys="ExpenseCategoryModel.created_by_user_id",
    )
    customers = relationship(
        "CustomerModel",
        back_populates="created_by_user",
        foreign_keys="CustomerModel.created_by_user_id",
    )

    suppliers = relationship(
        "SupplierModel",
        back_populates="created_by_user",
        foreign_keys="SupplierModel.created_by_user_id",
    )
    sale_payments = relationship(
        "SalePaymentModel",
        back_populates="received_by_user",
        foreign_keys="SalePaymentModel.received_by_user_id",
    )

    purchase_payments = relationship(
        "PurchasePaymentModel",
        back_populates="paid_by_user",
        foreign_keys="PurchasePaymentModel.paid_by_user_id",
    )

    inventory_movements = relationship(
        "InventoryMovementModel",
        back_populates="created_by_user",
        foreign_keys="InventoryMovementModel.created_by_user_id",
    )

    payment_methods = relationship("PaymentMethodModel", back_populates="created_by_user",
            foreign_keys="PaymentMethodModel.created_by_user_id",)

    jobs = relationship(
        "JobModel",
        back_populates="created_by_user",
        foreign_keys="JobModel.created_by_user_id",
    )

    job_payments = relationship(
        "JobPaymentModel",
        back_populates="received_by_user",
        foreign_keys="JobPaymentModel.received_by_user_id",
    )