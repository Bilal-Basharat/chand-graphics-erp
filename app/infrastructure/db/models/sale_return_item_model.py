from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, text
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

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
    )
    """How many came back, in the unit the invoice line was sold in. It
    carries no unit column of its own: a return is a reversal, and one
    measured differently from what it reverses could not be bounded by
    it."""

    base_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    """What came back in base units, converted the way the sale line was.

    Taken from the line being reversed rather than from the SKU's units as
    they stand today — reconfiguring a Box after the fact must not change
    how much stock a past return put back on the shelf.
    """

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
