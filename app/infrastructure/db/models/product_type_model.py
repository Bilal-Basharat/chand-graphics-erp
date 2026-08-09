from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class ProductTypeModel(Base, AuditMixin):
    """No price column on purpose — what a product sells for is agreed per
    job item, not held on the catalogue. See CardModel for the same rule."""

    __tablename__ = "product_types"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    job_items = relationship("JobItemModel", back_populates="product_type")
