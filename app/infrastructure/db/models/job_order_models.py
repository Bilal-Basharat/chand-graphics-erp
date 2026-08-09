"""
Tables behind the job order aggregate.

Grouped like the entities they carry: a job item is meaningless without
its job, and a material line without its item, so they are read together
and deleted together. Every child cascades from its parent — deleting a
job that was entered by mistake must not leave its material lines behind.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums.item_type import ItemType
from app.domain.enums.job_status import JobStatus
from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import AuditMixin, TimestampMixin
from app.shared.datetimes import now_pkt


class JobModel(Base, AuditMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    job_no: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        Enum(JobStatus, name="job_status_enum", native_enum=False),
        nullable=False,
        default=JobStatus.DRAFT,
        index=True,
    )

    promised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    balance_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    customer = relationship("CustomerModel", back_populates="jobs")
    created_by_user = relationship(
        "UserModel",
        back_populates="jobs",
        foreign_keys="JobModel.created_by_user_id",
    )
    items = relationship(
        "JobItemModel",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    payments = relationship(
        "JobPaymentModel",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class JobItemModel(Base, TimestampMixin):
    __tablename__ = "job_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_type_id: Mapped[int] = mapped_column(
        ForeignKey("product_types.id"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    specifications: Mapped[str | None] = mapped_column(String(500), nullable=True)

    job = relationship("JobModel", back_populates="items")
    product_type = relationship("ProductTypeModel", back_populates="job_items")
    materials = relationship(
        "JobMaterialModel",
        back_populates="job_item",
        cascade="all, delete-orphan",
    )
    labour_charges = relationship(
        "JobLabourChargeModel",
        back_populates="job_item",
        cascade="all, delete-orphan",
    )


class JobMaterialModel(Base, TimestampMixin):
    __tablename__ = "job_materials"

    __table_args__ = (
        CheckConstraint(
            "(card_id IS NOT NULL AND inventory_item_id IS NULL) OR "
            "(card_id IS NULL AND inventory_item_id IS NOT NULL)",
            name="ck_job_materials_exclusive_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    job_item_id: Mapped[int] = mapped_column(
        ForeignKey("job_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(
        Enum(ItemType, name="item_type_enum_job_materials", native_enum=False),
        nullable=False,
        index=True,
    )

    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), nullable=True, index=True)
    inventory_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id"),
        nullable=True,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Frozen at the moment the job was recorded — a later purchase at a
    # different price must not restate what work already done cost.
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    line_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    job_item = relationship("JobItemModel", back_populates="materials")
    card = relationship("CardModel")
    inventory_item = relationship("InventoryItemModel")


class JobLabourChargeModel(Base, TimestampMixin):
    __tablename__ = "job_labour_charges"

    id: Mapped[int] = mapped_column(primary_key=True)

    job_item_id: Mapped[int] = mapped_column(
        ForeignKey("job_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    labour_charge_type_id: Mapped[int] = mapped_column(
        ForeignKey("labour_charge_types.id"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    job_item = relationship("JobItemModel", back_populates="labour_charges")
    labour_charge_type = relationship("LabourChargeTypeModel", back_populates="charges")


class JobPaymentModel(Base, TimestampMixin):
    __tablename__ = "job_payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional and cleared on delete — see SalePaymentModel for why.
    payment_method_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    reference_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    received_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=now_pkt,
    )

    job = relationship("JobModel", back_populates="payments")
    payment_method = relationship("PaymentMethodModel", back_populates="job_payments")
    received_by_user = relationship("UserModel", back_populates="job_payments")
