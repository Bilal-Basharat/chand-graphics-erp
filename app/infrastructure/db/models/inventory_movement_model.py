from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.infrastructure.db.mixins import AuditMixin
from app.infrastructure.db.base import Base

class InventoryMovementModel(Base, AuditMixin):
    __tablename__ = "inventory_movements"

    __table_args__ = (
        CheckConstraint(
           "(card_id IS NOT NULL AND inventory_item_id IS NULL) OR "
            "(card_id IS NULL AND inventory_item_id IS NOT NULL)",
            name="ck_inventory_movements_exclusive_target",
        ),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)

    movement_type: Mapped[str] = mapped_column(
        Enum(MovementType, name="movement_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        Enum(ItemType),
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

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
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
        default=datetime.utcnow,
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

    card = relationship("CardModel")
    inventory_item = relationship("InventoryItemModel")
    created_by_user = relationship("UserModel")