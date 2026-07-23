from datetime import datetime

from sqlalchemy import DateTime, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(
        String(50),
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    sales = relationship("SaleModel", back_populates="created_by_user")
    purchases = relationship("PurchaseModel", back_populates="created_by_user")
    expenses = relationship("ExpenseModel", back_populates="created_by_user")
    customers = relationship("CustomerModel", back_populates="created_by_user")

    suppliers = relationship("SupplierModel", back_populates="created_by_user")
    sale_payments = relationship("SalePaymentModel", back_populates="received_by_user")

    purchase_payments = relationship("PurchasePaymentModel", back_populates="paid_by_user")
