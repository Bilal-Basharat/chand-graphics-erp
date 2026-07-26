from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.entities.expense import Expense
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.entities.purchase import Purchase
from app.domain.entities.purchase_payment import PurchasePayment
from app.domain.entities.sale import Sale
from app.domain.entities.sale_payment import SalePayment
from app.domain.repositories.expense_repository import ExpenseRepository as ExpenseRepositoryPort
from app.domain.repositories.inventory_movement_repository import (
    InventoryMovementRepository as InventoryMovementRepositoryPort,
)
from app.domain.repositories.purchase_payment_repository import (
    PurchasePaymentRepository as PurchasePaymentRepositoryPort,
)
from app.domain.repositories.purchase_repository import PurchaseRepository as PurchaseRepositoryPort
from app.domain.repositories.sale_payment_repository import (
    SalePaymentRepository as SalePaymentRepositoryPort,
)
from app.domain.repositories.sale_repository import SaleRepository as SaleRepositoryPort
from app.infrastructure.db.models.expense_model import ExpenseModel
from app.infrastructure.db.models.inventory_movement_model import InventoryMovementModel
from app.infrastructure.db.models.purchase_model import PurchaseModel
from app.infrastructure.db.models.purchase_payment_model import PurchasePaymentModel
from app.infrastructure.db.models.sale_model import SaleModel
from app.infrastructure.db.models.sale_payment_model import SalePaymentModel
from app.infrastructure.mappers.expense_mapper import ExpenseMapper
from app.infrastructure.mappers.inventory_movement_mapper import InventoryMovementMapper
from app.infrastructure.mappers.purchase_mapper import PurchaseMapper
from app.infrastructure.mappers.purchase_payment_mapper import PurchasePaymentMapper
from app.infrastructure.mappers.sale_mapper import SaleMapper
from app.infrastructure.mappers.sale_payment_mapper import SalePaymentMapper
from app.infrastructure.repositories.base import SQLAlchemyRepository


class SqlAlchemyExpenseRepository(
    SQLAlchemyRepository[Expense, ExpenseModel],
    ExpenseRepositoryPort,
):
    """
    Persistence for expense records.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, ExpenseModel, ExpenseMapper)

    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[Expense]:
        stmt = (
            select(ExpenseModel)
            .where(ExpenseModel.created_at >= start)
            .where(ExpenseModel.created_at <= end)
            .order_by(ExpenseModel.created_at.desc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [ExpenseMapper.to_entity(model) for model in models]

    def list_by_category(self, category_id: int, limit: int = 200) -> list[Expense]:
        stmt = (
            select(ExpenseModel)
            .where(ExpenseModel.category_id == category_id)
            .order_by(ExpenseModel.created_at.desc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [ExpenseMapper.to_entity(model) for model in models]


class SqlAlchemyPurchaseRepository(
    SQLAlchemyRepository[Purchase, PurchaseModel],
    PurchaseRepositoryPort,
):
    """
    Persistence for purchase headers with their items and payments.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, PurchaseModel, PurchaseMapper)

    def get_by_purchase_no(self, purchase_no: str) -> Purchase | None:
        stmt = (
            select(PurchaseModel)
            .where(PurchaseModel.purchase_no == purchase_no)
            .options(
                selectinload(PurchaseModel.items),
                selectinload(PurchaseModel.payments),
            )
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else PurchaseMapper.to_entity(model)

    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ) -> list[Purchase]:
        stmt = (
            select(PurchaseModel)
            .where(PurchaseModel.created_at >= start)
            .where(PurchaseModel.created_at <= end)
            .order_by(PurchaseModel.created_at.desc())
            .options(
                selectinload(PurchaseModel.items),
                selectinload(PurchaseModel.payments),
            )
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [PurchaseMapper.to_entity(model) for model in models]


class SqlAlchemySaleRepository(
    SQLAlchemyRepository[Sale, SaleModel],
    SaleRepositoryPort,
):
    """
    Persistence for sale headers with their items and payments.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, SaleModel, SaleMapper)

    def get_by_invoice_no(self, invoice_no: str) -> Sale | None:
        stmt = (
            select(SaleModel)
            .where(SaleModel.invoice_no == invoice_no)
            .options(
                selectinload(SaleModel.items),
                selectinload(SaleModel.payments),
            )
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else SaleMapper.to_entity(model)

    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ) -> list[Sale]:
        stmt = (
            select(SaleModel)
            .where(SaleModel.created_at >= start)
            .where(SaleModel.created_at <= end)
            .order_by(SaleModel.created_at.desc())
            .options(
                selectinload(SaleModel.items),
                selectinload(SaleModel.payments),
            )
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [SaleMapper.to_entity(model) for model in models]


class SqlAlchemyPurchasePaymentRepository(
    SQLAlchemyRepository[PurchasePayment, PurchasePaymentModel],
    PurchasePaymentRepositoryPort,
):
    """
    Persistence for purchase payments.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, PurchasePaymentModel, PurchasePaymentMapper)

    def list_by_purchase_id(self, purchase_id: int) -> list[PurchasePayment]:
        stmt = (
            select(PurchasePaymentModel)
            .where(PurchasePaymentModel.purchase_id == purchase_id)
            .order_by(PurchasePaymentModel.paid_at.asc())
        )
        models = self.session.execute(stmt).scalars().all()
        return [PurchasePaymentMapper.to_entity(model) for model in models]


class SqlAlchemySalePaymentRepository(
    SQLAlchemyRepository[SalePayment, SalePaymentModel],
    SalePaymentRepositoryPort,
):
    """
    Persistence for sale payments.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, SalePaymentModel, SalePaymentMapper)

    def list_by_sale_id(self, sale_id: int) -> list[SalePayment]:
        stmt = (
            select(SalePaymentModel)
            .where(SalePaymentModel.sale_id == sale_id)
            .order_by(SalePaymentModel.received_at.asc())
        )
        models = self.session.execute(stmt).scalars().all()
        return [SalePaymentMapper.to_entity(model) for model in models]


class SqlAlchemyInventoryMovementRepository(
    SQLAlchemyRepository[InventoryMovement, InventoryMovementModel],
    InventoryMovementRepositoryPort,
):
    """
    Persistence for special stock movements:
    adjustments, transfers, damages, and returns.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, InventoryMovementModel, InventoryMovementMapper)

    def list_by_source_document(
        self,
        source_document_type: str,
        source_document_id: int,
        limit: int = 200,
    ) -> list[InventoryMovement]:
        stmt = (
            select(InventoryMovementModel)
            .where(InventoryMovementModel.source_document_type == source_document_type)
            .where(InventoryMovementModel.source_document_id == source_document_id)
            .order_by(InventoryMovementModel.occurred_at.desc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [InventoryMovementMapper.to_entity(model) for model in models]