from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.item_type import ItemType
from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class SaleReturnItemModel(Base, TimestampMixin):
    """One returned line off one sale return — see `SaleItemModel`.

    Its own table rather than columns on the return, because a customer
    hands back several things at once and that is one return with several
    lines, exactly as a sale is one invoice with several.
    """

    __tablename__ = "sale_return_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    sale_return_id: Mapped[int] = mapped_column(
        ForeignKey("sale_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sale_item_id: Mapped[int] = mapped_column(
        ForeignKey("sale_items.id"),
        nullable=False,
        index=True,
    )
    """Which line of the invoice came back. Indexed because every return
    is validated by totalling the quantity already returned off its
    line."""

    item_type: Mapped[str] = mapped_column(
        Enum(ItemType, name="item_type_enum_sale_return_items", native_enum=False),
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

    sale_return = relationship("SaleReturnModel", back_populates="items")
    sale_item = relationship("SaleItemModel")
    inventory_item = relationship("InventoryItemModel")
