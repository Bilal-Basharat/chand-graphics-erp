from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class SkuUnitModel(Base, AuditMixin):
    """One alternate way of counting one SKU — "a Box is 288 Pieces".

    Only alternates are rows. A SKU's base unit is the word on the SKU
    itself, worth one of itself, so it has no row here and cannot fall
    out of step with one. A document line naming no unit was entered in
    the base unit, which is why every line written before this table
    existed reads back correctly.
    """

    __tablename__ = "sku_units"
    __table_args__ = (UniqueConstraint("sku_id", "name", name="uq_sku_units_sku_id_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    sku_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_items.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    factor: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
    )
    """How many base units one of these is worth.

    Four decimal places, like every quantity: a unit worth an eighth of a
    base unit is an ordinary thing to sell, and rounding it to a whole
    number would make the count drift every time one was traded.
    """

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    """Whether it may still be chosen on a new document.

    Retired rather than deleted, because the documents that used it are
    read back through it: a unit that vanished would leave them naming
    nothing, and their base quantities unexplained.
    """

    #############################################################
    #################### relationship methods ###################
    #############################################################

    sku = relationship(
        "InventoryItemModel",
        back_populates="units",
        foreign_keys="SkuUnitModel.sku_id",
    )
