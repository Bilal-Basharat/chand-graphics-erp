from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class InventoryItemModel(Base, AuditMixin):
    """
    No price columns here on purpose — purchase/selling price lives on
    PurchaseItemModel/SaleItemModel.unit_price, per transaction.
    """

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
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

    unit: Mapped[str | None] = mapped_column(
        String(20),
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
    )

    sale_items = relationship(
        "SaleItemModel",
        back_populates="inventory_item",
    )