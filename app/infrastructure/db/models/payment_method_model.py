from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class PaymentMethodModel(Base, TimestampMixin):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    sale_payments = relationship(
    "SalePaymentModel",
    back_populates="payment_method",
    )

    purchase_payments = relationship(
    "PurchasePaymentModel",
    back_populates="payment_method",
    )