from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, text
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

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=1,
    )
    """How many were sold, in the unit the line was entered in — see
    `uom_id`. This is what the invoice reads, not what the shelf moved
    by."""

    uom_id: Mapped[int | None] = mapped_column(
        ForeignKey("sku_units.id"),
        nullable=True,
        index=True,
    )
    """Which of the SKU's units this line was entered in, or NULL for its
    base unit. NULL is not a gap: it is how every line written before
    units existed reads, and it is correct for all of them."""

    base_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    """The same quantity in the SKU's base unit — what stock moved by and
    what `unit_cost` multiplies.

    Stored rather than re-derived, and that is the whole point of the
    column: a conversion corrected next year must not restate an invoice
    handed over last year.
    """

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
    """What one **base unit** of this had cost to buy, as at the moment it
    was sold.

    Per base unit, not per unit sold: the average it comes from is taken
    over base quantities, so a line sold by the Box multiplies this by its
    `base_quantity`. Both sides in the same unit, or the margin on a box
    would be read at a piece's cost.

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

    previous_stock: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        nullable=True,
    )

    resulting_stock: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
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