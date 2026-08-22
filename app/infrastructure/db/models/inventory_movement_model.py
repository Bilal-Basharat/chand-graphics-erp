from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.infrastructure.db.mixins import AuditMixin
from app.infrastructure.db.base import Base
from app.shared.datetimes import now_pkt

class InventoryMovementModel(Base, AuditMixin):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True)

    movement_type: Mapped[str] = mapped_column(
        Enum(MovementType, name="movement_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        Enum(ItemType, name="item_type_enum_inventory_movements", native_enum=False),
        nullable=False,
        index=True,
    )

    source_document_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    source_document_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
    )
    """The size of the movement, in the unit it was recorded in. Always
    positive; which way it moved the count is read from the two stock
    figures below."""

    uom_id: Mapped[int | None] = mapped_column(
        ForeignKey("sku_units.id"),
        nullable=True,
        index=True,
    )
    """Which of the SKU's units, or NULL for its base unit — see
    `SaleItemModel.uom_id`."""

    base_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    """The same, in base units: what the shelf actually moved by. An
    adjustment of one Box takes 288 Pieces off the count, and the register
    has to be able to show both."""

    unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
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

    reference_no: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=now_pkt,
    )

    inventory_item_id: Mapped[int] = mapped_column(
            ForeignKey("inventory_items.id"),
            nullable=False,
            index=True,
    )
    """Which catalogue record the stock moved on — see SaleItemModel."""

    inventory_item = relationship("InventoryItemModel")
    created_by_user = relationship("UserModel", foreign_keys="InventoryMovementModel.created_by_user_id", back_populates="inventory_movements")
