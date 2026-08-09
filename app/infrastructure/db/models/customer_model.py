from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class CustomerModel(Base, AuditMixin):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    
    #############################################################
    #################### relationship methods ###################
    #############################################################

    sales = relationship("SaleModel", back_populates="customer")
    jobs = relationship("JobModel", back_populates="customer")
    created_by_user = relationship(
        "UserModel",
        back_populates="customers",
        foreign_keys="CustomerModel.created_by_user_id",
    )