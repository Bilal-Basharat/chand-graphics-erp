from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class PurchaseModel(Base, AuditMixin):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)

    purchase_no: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    grand_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    balance_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    reference_no: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"),
        nullable=True,
        index=True,
    )

    # created_by_user_id: Mapped[int | None] = mapped_column(
    #     ForeignKey("users.id"),
    #     nullable=True,
    #     index=True,
    # )

    # created_at: Mapped[datetime] = mapped_column(
    #     DateTime,
    #     nullable=False,
    #     default=datetime.utcnow,
    # )

#############################################################
#################### relationship methods ###################
#############################################################
 
    supplier = relationship("SupplierModel", back_populates="purchases")
    created_by_user = relationship("UserModel", back_populates="purchases")

    items = relationship(
        "PurchaseItemModel",
        back_populates="purchase",
        cascade="all, delete-orphan",)

    payments = relationship("PurchasePaymentModel", back_populates="purchase")