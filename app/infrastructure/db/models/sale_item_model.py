from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class SaleItemModel(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id"),
        nullable=False,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    card_id: Mapped[int | None] = mapped_column(
        ForeignKey("cards.id"),
        nullable=True,
        index=True,
    )

    inventory_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id"),
        nullable=True,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    sale = relationship("SaleModel", back_populates="items")
    card = relationship("CardModel", back_populates="sale_items")
    inventory_item = relationship("InventoryItemModel", back_populates="sale_items")