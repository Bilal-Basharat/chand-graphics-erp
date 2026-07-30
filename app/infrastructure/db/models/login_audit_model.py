from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import TimestampMixin


class LoginAuditModel(Base, TimestampMixin):
    __tablename__ = "login_audits"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)