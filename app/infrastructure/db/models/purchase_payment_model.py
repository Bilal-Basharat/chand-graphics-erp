from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class PurchasePaymentModel(Base, TimestampMixin):
    __tablename__ = "purchase_payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("purchases.id"),
        nullable=False,
        index=True,
    )

    # Optional and cleared on delete — see SalePaymentModel for why.
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

    paid_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    paid_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    purchase = relationship(
        "PurchaseModel",
        back_populates="payments",
    )

    payment_method = relationship(
        "PaymentMethodModel",
        back_populates="purchase_payments",
    )

    paid_by_user = relationship(
        "UserModel",
        back_populates="purchase_payments",
    )