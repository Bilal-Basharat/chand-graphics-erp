from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin


class ExpenseCategoryModel(Base, AuditMixin):
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    #############################################################
    #################### relationship methods ###################
    #############################################################

    expenses = relationship("ExpenseModel", foreign_keys=("ExpenseModel.category_id"), back_populates="category")

    created_by_user = relationship(
        "UserModel",
        back_populates="expense_categories",
        foreign_keys="ExpenseCategoryModel.created_by_user_id",
    )