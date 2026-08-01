from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class PaymentMethodModel(Base, AuditMixin):
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

    created_by_user = relationship("UserModel", back_populates="payment_methods", foreign_keys="PaymentMethodModel.created_by_user_id")

    sale_payments = relationship(
    "SalePaymentModel",
    back_populates="payment_method",
    )

    purchase_payments = relationship(
    "PurchasePaymentModel",
    back_populates="payment_method",
    )