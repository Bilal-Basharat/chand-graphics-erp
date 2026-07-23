from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class CabinetModel(Base):
    __tablename__ = "cabinets"

    id: Mapped[int] = mapped_column(primary_key=True)

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

#############################################################
#################### relationship methods ###################
#############################################################

    cards = relationship(
        "CardModel",
        back_populates="cabinet",
    )