from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin
from app.shared.datetimes import now_pkt


class SaleReturnModel(Base, AuditMixin):
    """Goods off one sale, coming back — the header of the return.

    A document with lines of its own, because a customer hands back
    several things at once and that is one return, one number and one
    decision about the refund. What came back off which invoice line is
    in `sale_return_items`.

    Not a relationship on `SaleModel`. Its mapper rebuilds the sale's
    collections wholesale before merging, so a third cascading collection
    would be wiped by the next payment recorded against the invoice.
    """

    __tablename__ = "sale_returns"

    id: Mapped[int] = mapped_column(primary_key=True)

    return_no: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id"),
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
    """Indexed: the customer ledger reads returns by date window."""

    #############################################################
    #################### relationship methods ###################
    #############################################################

    sale = relationship("SaleModel")
    items = relationship(
        "SaleReturnItemModel",
        back_populates="sale_return",
        cascade="all, delete-orphan",
    )
    refund_method = relationship("PaymentMethodModel")
