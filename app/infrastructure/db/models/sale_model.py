from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class SaleModel(Base, AuditMixin):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)

    invoice_no: Mapped[str] = mapped_column(
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

    customer_id: Mapped[int | None] = mapped_column(
            ForeignKey("customers.id"),
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

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    customer = relationship("CustomerModel", back_populates="sales")
    created_by_user = relationship("UserModel", back_populates="sales")
    items = relationship(
        "SaleItemModel",
        back_populates="sale",
        cascade="all, delete-orphan",
    )

    payments = relationship(
    "SalePaymentModel",
    back_populates="sale",
    cascade="all, delete-orphan",
    )