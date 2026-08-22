from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class InventoryItemModel(Base, AuditMixin):
    """
    The SKU: the stock identity a count belongs to and a document line
    names. The product above it is the business identity.

    No price columns here on purpose — purchase/selling price lives on
    PurchaseItemModel/SaleItemModel.unit_price, per transaction.

    **On the quantity columns.** They are `Numeric(14, 4)` here while a
    database already in the field still declares them `INTEGER`. SQLite's
    declared types are affinity, not constraint: an INTEGER-affinity
    column stores 0.5 as REAL and hands it back unchanged, so both files
    behave identically and no table had to be rebuilt to sell half a
    sheet. What the models say is what a fresh database — and any future
    non-SQLite one — is built from.
    """

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )
    """What this SKU is called on an invoice. For a product with one SKU
    — nearly all of them — it is the product's own name, kept in step by
    `RenameProductUseCase`."""

    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"),
        nullable=True,
        index=True,
    )
    """Which product this is a variant of.

    Nullable in the column only. Every SKU has one; a database that
    predates products has each of its items given one by
    `_add_catalogue_grouping`, and nothing creates a SKU without one.
    """

    current_stock: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
        nullable=False,
        default=0,
    )
    """How many **base units** are on the shelf. Ten boxes of 288 is
    2,880 here, with `unit` reading "Piece"."""

    minimum_stock: Mapped[Decimal] = mapped_column(
        Numeric(14, 4),
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
    """The **base unit**: the word the two counts above are counted in.
    Alternates live in `sku_units` and say how many of these they are."""

    cabinet_id: Mapped[int | None] = mapped_column(
        ForeignKey("cabinets.id"),
        nullable=True,
        index=True,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    created_by_user = relationship(
                "UserModel",
                back_populates="inventory_items",
                foreign_keys="InventoryItemModel.created_by_user_id",
    )

    cabinet = relationship(
        "CabinetModel",
        back_populates="inventory_items",
        foreign_keys="InventoryItemModel.cabinet_id",
    )

    product = relationship(
        "ProductModel",
        back_populates="skus",
        foreign_keys="InventoryItemModel.product_id",
    )

    units = relationship(
        "SkuUnitModel",
        back_populates="sku",
        foreign_keys="SkuUnitModel.sku_id",
        cascade="all, delete-orphan",
    )
    """Its alternate units. Deleted with it: a unit belongs to one SKU and
    means nothing without it. A SKU that has ever traded cannot be deleted
    at all, so this never takes a unit a document still reads."""

    purchase_items = relationship(
        "PurchaseItemModel",
        back_populates="inventory_item",
    )

    sale_items = relationship(
        "SaleItemModel",
        back_populates="inventory_item",
    )
