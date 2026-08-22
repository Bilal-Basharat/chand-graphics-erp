from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class ProductModel(Base, AuditMixin):
    """What the shop calls a thing it trades in.

    Holds no stock, no unit and no price — those are the SKU's, and a
    product that carried its own would contradict them the moment it grew
    a second variant.
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
        index=True,
    )
    """Which shelf it is listed on.

    Required, because a product filed nowhere is one that falls out of
    the catalogue. There is always a `General` to fall back to, so this
    never has to be a question the shopkeeper is asked.
    """

    #############################################################
    #################### relationship methods ###################
    #############################################################

    category = relationship(
        "CategoryModel",
        back_populates="products",
        foreign_keys="ProductModel.category_id",
    )

    skus = relationship(
        "InventoryItemModel",
        back_populates="product",
        foreign_keys="InventoryItemModel.product_id",
    )
