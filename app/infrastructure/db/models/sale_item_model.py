from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.item_type import ItemType
from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class SaleItemModel(Base, TimestampMixin):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        Enum(ItemType, name="item_type_enum_sale_items", native_enum=False),
        nullable=False,
        index=True,
    )

    inventory_item_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id"),
        nullable=False,
        index=True,
    )
    """Which catalogue record the line sold. A special item module adds
    its own nullable column beside this one, and a CHECK constraint
    naming exactly one of them — see ItemType."""

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

    sale = relationship("SaleModel", back_populates="items")
    inventory_item = relationship("InventoryItemModel", back_populates="sale_items")