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

    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    """What one of these had cost to buy, as at the moment it was sold.

    Written once, when the sale is raised, and never revisited — buying
    the item again next month must not rewrite last month's margin. It is
    the quantity-weighted average of every purchase of the item up to that
    day, which is what an ERP calls a valuation rate.

    Nullable because an item that has never been bought has no such
    figure. **That is not zero.** Read as zero it would report the whole
    line as profit, so every report counts these lines and says so rather
    than quietly adding them in.
    """

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