from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class ExpenseModel(Base, AuditMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)

    expense_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        default=0,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    remarks: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("expense_categories.id"),
        nullable=True,
        index=True,
    )

    #############################################################
    #################### relationship methods ###################
    #############################################################

    created_by_user = relationship(
        "UserModel",
        back_populates="expenses",
        foreign_keys="ExpenseModel.created_by_user_id",
    )
    category = relationship("ExpenseCategoryModel", foreign_keys=("ExpenseModel.category_id"), back_populates="expenses")