from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.item_type import ItemType
from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class PurchaseItemModel(Base, TimestampMixin):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("purchases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        Enum(ItemType, name="item_type_enum_purchase_items", native_enum=False),
        nullable=False,
        index=True,
    )

    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id"),
        nullable=False,
        index=True,
    )
    """Which catalogue record the line bought — see SaleItemModel."""

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    unit_price: Mapped[Decimal] = mapped_column(
            Numeric(12, 2),
            nullable=False,
            default=0,
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    previous_stock: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    resulting_stock: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    #############################################################
    #################### relationship methods ###################
    #############################################################

    purchase = relationship("PurchaseModel", back_populates="items")
    inventory_item = relationship("InventoryItemModel", back_populates="purchase_items")
