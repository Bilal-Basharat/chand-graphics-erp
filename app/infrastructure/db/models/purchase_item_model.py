from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.item_type import ItemType
from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class PurchaseItemModel(Base, TimestampMixin):
    __tablename__ = "purchase_items"

    __table_args__ = (
        CheckConstraint(
           "(card_id IS NOT NULL AND inventory_item_id IS NULL) OR "
        "(card_id IS NULL AND inventory_item_id IS NOT NULL)",
        name="ck_purchase_items_exclusive_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("purchases.id"),
        nullable=False,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        Enum(ItemType, name="item_type_enum", native_enum=False),
        nullable=False,
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

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
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

    previous_stock: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    resulting_stock: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    purchase = relationship("PurchaseModel", back_populates="items")
    card = relationship("CardModel", back_populates="purchase_items")
    inventory_item = relationship("InventoryItemModel", back_populates="purchase_items")