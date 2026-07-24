from sqlalchemy import ForeignKey, String
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

    # created_by_user_id: Mapped[int | None] = mapped_column(
    #         ForeignKey("users.id"),
    #         nullable=True,
    #         index=True,
    # )

#############################################################
#################### relationship methods ###################
#############################################################

    purchases = relationship("PurchaseModel", back_populates="supplier")
    created_by_user = relationship("UserModel", back_populates="suppliers")