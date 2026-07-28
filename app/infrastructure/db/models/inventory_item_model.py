from decimal import Decimal

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class InventoryItemModel(Base, AuditMixin):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    selling_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    current_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    minimum_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    created_by_user = relationship(
                "UserModel",
                back_populates="inventory_items",
                foreign_keys="InventoryItemModel.created_by_user_id",
    )
    
    purchase_items = relationship(
        "PurchaseItemModel",
        back_populates="inventory_item",
        cascade="all, delete-orphan",
    )

    sale_items = relationship(
        "SaleItemModel",
        back_populates="inventory_item",
        cascade="all, delete-orphan",
    )