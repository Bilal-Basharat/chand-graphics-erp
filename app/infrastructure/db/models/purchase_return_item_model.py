from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.item_type import ItemType
from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class PurchaseReturnItemModel(Base, TimestampMixin):
    """One line off one purchase return — the mirror of
    `SaleReturnItemModel`."""

    __tablename__ = "purchase_return_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    purchase_return_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purchase_item_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_items.id"),
        nullable=False,
        index=True,
    )
    """Which line of the bill went back — see `SaleReturnItemModel`."""

    item_type: Mapped[str] = mapped_column(
        Enum(ItemType, name="item_type_enum_purchase_return_items", native_enum=False),
        nullable=False,
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

    #############################################################
    #################### relationship methods ###################
    #############################################################

    purchase_return = relationship("PurchaseReturnModel", back_populates="items")
    purchase_item = relationship("PurchaseItemModel")
    inventory_item = relationship("InventoryItemModel")
