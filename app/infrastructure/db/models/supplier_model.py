from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class SupplierModel(Base, AuditMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # What was owed before this software existed. Not derived from any
    # purchase, so it has to be stored rather than computed.
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0",
    )

    #############################################################
    #################### relationship methods ###################
    #############################################################

    purchases = relationship("PurchaseModel", back_populates="supplier")
    created_by_user = relationship(
        "UserModel",
        back_populates="suppliers",
        foreign_keys="SupplierModel.created_by_user_id",
    )