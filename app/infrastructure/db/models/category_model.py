from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class CategoryModel(Base, AuditMixin):
    """A shelf in the catalogue. Groups products and holds nothing else.

    No unique constraint on the name: the application refuses a duplicate
    with a message a shopkeeper can act on, the same way inventory items
    and cabinets are handled, and a driver-level integrity error could
    only be reported as "something went wrong".
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    #############################################################
    #################### relationship methods ###################
    #############################################################

    products = relationship(
        "ProductModel",
        back_populates="category",
        foreign_keys="ProductModel.category_id",
    )
