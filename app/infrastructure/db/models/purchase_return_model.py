from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin
from app.shared.datetimes import now_pkt


class PurchaseReturnModel(Base, AuditMixin):
    """Goods off one purchase, going back — the header of the return.

    The mirror of `SaleReturnModel`; its lines are in
    `purchase_return_items`, and it is deliberately not a relationship on
    `PurchaseModel` for the same reason.
    """

    __tablename__ = "purchase_returns"

    id: Mapped[int] = mapped_column(primary_key=True)

    return_no: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("purchases.id"),
        nullable=False,
        index=True,
    )

    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    # Cleared rather than blocking when the method it names is deleted —
    # see SalePaymentModel.payment_method_id.
    refund_method_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    returned_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=now_pkt,
        index=True,
    )
    """Indexed: the supplier ledger reads returns by date window."""

    #############################################################
    #################### relationship methods ###################
    #############################################################

    purchase = relationship("PurchaseModel")
    items = relationship(
        "PurchaseReturnItemModel",
        back_populates="purchase_return",
        cascade="all, delete-orphan",
    )
    refund_method = relationship("PaymentMethodModel")
