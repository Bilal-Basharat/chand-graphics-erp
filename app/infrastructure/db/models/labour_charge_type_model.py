from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class LabourChargeTypeModel(Base, AuditMixin):
    """The kinds of work the shop charges for. The money is on the charge
    itself, not here — see LabourChargeType."""

    __tablename__ = "labour_charge_types"

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

    charges = relationship("JobLabourChargeModel", back_populates="labour_charge_type")
