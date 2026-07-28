from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class CabinetModel(Base, AuditMixin):
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
        foreign_keys="CardModel.cabinet_id",
    )

    created_by_user = relationship(
        "UserModel",
        back_populates="cabinets",
        foreign_keys="CabinetModel.created_by_user_id",
    )