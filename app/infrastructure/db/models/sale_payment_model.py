from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class SalePaymentModel(Base, TimestampMixin):
    __tablename__ = "sale_payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id"),
        nullable=False,
        index=True,
    )

    # Optional, and cleared rather than blocking when the method it names
    # is deleted: a payment that was made is a fact, and it should not be
    # undeletable master data that keeps it on the books.
    payment_method_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    reference_no: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    received_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    sale = relationship(
        "SaleModel",
        back_populates="payments",
    )

    payment_method = relationship(
        "PaymentMethodModel",
        back_populates="sale_payments",
    )

    received_by_user = relationship(
        "UserModel",
        back_populates="sale_payments",
    )