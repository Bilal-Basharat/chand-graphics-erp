from decimal import Decimal
from sqlalchemy import ForeignKey, Integer, String, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class CardModel(Base, AuditMixin):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)

    card_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=True,
    )

    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    selling_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    current_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    minimum_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    cabinet_id: Mapped[int | None] = mapped_column(
        ForeignKey("cabinets.id"),
        nullable=True,
        index=True,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    created_by_user = relationship(
            "UserModel",
            back_populates="cards",
            foreign_keys="CardModel.created_by_user_id",
    )
    
    cabinet = relationship(
        "CabinetModel",
        back_populates="cards",
        foreign_keys="CardModel.cabinet_id",
    )

    purchase_items = relationship(
        "PurchaseItemModel",
        back_populates="card",
    )

    sale_items = relationship(
        "SaleItemModel",
        back_populates="card",
    )