from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.entities.expense import Expense
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.entities.purchase import Purchase
from app.domain.entities.purchase_payment import PurchasePayment
from app.domain.entities.sale import Sale
from app.domain.entities.sale_payment import SalePayment
from app.domain.enums.item_type import ItemType
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
from app.infrastructure.db.models.customer_model import CustomerModel
from app.infrastructure.db.models.purchase_item_model import PurchaseItemModel
from app.infrastructure.db.models.purchase_model import PurchaseModel
from app.infrastructure.db.models.purchase_payment_model import PurchasePaymentModel
from app.infrastructure.db.models.sale_item_model import SaleItemModel
from app.infrastructure.db.models.sale_model import SaleModel
from app.infrastructure.db.models.sale_payment_model import SalePaymentModel
from app.infrastructure.db.models.supplier_model import SupplierModel
from app.infrastructure.mappers.expense_mapper import ExpenseMapper
from app.infrastructure.mappers.inventory_movement_mapper import InventoryMovementMapper
from app.infrastructure.mappers.purchase_mapper import PurchaseMapper
from app.infrastructure.mappers.purchase_payment_mapper import PurchasePaymentMapper
from app.infrastructure.mappers.sale_mapper import SaleMapper
from app.infrastructure.mappers.sale_payment_mapper import SalePaymentMapper
from app.infrastructure.repositories.base import SQLAlchemyRepository


def _count_documents_holding_item(
    session: Session,
    line_model,
    document_column,
    item_type: ItemType,
    item_id: int,
) -> int:
    """How many documents have a line pointing at one card or inventory item.

    Sale lines and purchase lines are the same shape, so the query is
    written once. Documents rather than lines: a card listed twice on one
    invoice is still one invoice standing in the way of deleting it.
    """
    column = (
        line_model.card_id if item_type is ItemType.CARD else line_model.inventory_item_id
    )
    stmt = select(func.count(func.distinct(document_column))).where(column == item_id)
    return int(session.execute(stmt).scalar_one())


############################################################
################### Expense Repository ####################
############################################################
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

    def count_by_category(self, category_id: int) -> int:
        stmt = select(func.count(ExpenseModel.id)).where(
            ExpenseModel.category_id == category_id
        )
        return int(self.session.execute(stmt).scalar_one())


############################################################
################### Purchase Repository ####################
############################################################
class SqlAlchemyPurchaseRepository(
    SQLAlchemyRepository[Purchase, PurchaseModel],
    PurchaseRepositoryPort,
):
    """
    Persistence for purchase headers with their items and payments.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, PurchaseModel, PurchaseMapper)

    def get_by_id(self, entity_id: int) -> Purchase | None:
        stmt = (
            select(PurchaseModel)
            .where(PurchaseModel.id == entity_id)
            .options(
                selectinload(PurchaseModel.items),
                selectinload(PurchaseModel.payments),
            )
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else PurchaseMapper.to_entity(model)

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

    def search_by_term(self, term: str, limit: int = 50) -> list[Purchase]:
        pattern = f"%{term.strip()}%"
        stmt = (
            select(PurchaseModel)
            # Outer join: a purchase with no supplier still has to be
            # findable by its own number.
            .outerjoin(SupplierModel, PurchaseModel.supplier_id == SupplierModel.id)
            .where(
                or_(
                    PurchaseModel.purchase_no.ilike(pattern),
                    SupplierModel.name.ilike(pattern),
                    PurchaseModel.reference_no.ilike(pattern),
                    PurchaseModel.note.ilike(pattern),
                )
            )
            .order_by(PurchaseModel.created_at.desc())
            .options(
                selectinload(PurchaseModel.items),
                selectinload(PurchaseModel.payments),
            )
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [PurchaseMapper.to_entity(model) for model in models]

    def sum_by_supplier(self, supplier_id: int) -> Decimal:
        stmt = select(func.coalesce(func.sum(PurchaseModel.grand_total), 0)).where(
            PurchaseModel.supplier_id == supplier_id
        )
        total = self.session.execute(stmt).scalar_one()
        return Decimal(total)

    def count_by_item(self, item_type: ItemType, item_id: int) -> int:
        return _count_documents_holding_item(
            self.session, PurchaseItemModel, PurchaseItemModel.purchase_id, item_type, item_id
        )

    def latest_unit_price(self, item_type: ItemType, item_id: int) -> Decimal | None:
        column = (
            PurchaseItemModel.card_id
            if item_type is ItemType.CARD
            else PurchaseItemModel.inventory_item_id
        )
        stmt = (
            select(PurchaseItemModel.unit_price)
            .join(PurchaseModel, PurchaseItemModel.purchase_id == PurchaseModel.id)
            .where(column == item_id)
            # Newest purchase wins; id breaks the tie when two land in the
            # same second, which bulk entry routinely does.
            .order_by(PurchaseModel.created_at.desc(), PurchaseItemModel.id.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def count_by_supplier(self, supplier_id: int) -> int:
        stmt = select(func.count(PurchaseModel.id)).where(
            PurchaseModel.supplier_id == supplier_id
        )
        return int(self.session.execute(stmt).scalar_one())


############################################################
################### Sale Repository ####################
############################################################
class SqlAlchemySaleRepository(
    SQLAlchemyRepository[Sale, SaleModel],
    SaleRepositoryPort,
):
    """
    Persistence for sale headers with their items and payments.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, SaleModel, SaleMapper)

    def get_by_id(self, entity_id: int) -> Sale | None:
        stmt = (
            select(SaleModel)
            .where(SaleModel.id == entity_id)
            .options(
                selectinload(SaleModel.items),
                selectinload(SaleModel.payments),
            )
        )
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else SaleMapper.to_entity(model)

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

    def search_by_term(self, term: str, limit: int = 50) -> list[Sale]:
        pattern = f"%{term.strip()}%"
        stmt = (
            select(SaleModel)
            # Outer join: a walk-in sale has no customer and still has to
            # be findable by its invoice number.
            .outerjoin(CustomerModel, SaleModel.customer_id == CustomerModel.id)
            .where(
                or_(
                    SaleModel.invoice_no.ilike(pattern),
                    CustomerModel.name.ilike(pattern),
                    SaleModel.note.ilike(pattern),
                )
            )
            .order_by(SaleModel.created_at.desc())
            .options(
                selectinload(SaleModel.items),
                selectinload(SaleModel.payments),
            )
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [SaleMapper.to_entity(model) for model in models]

    def count_by_item(self, item_type: ItemType, item_id: int) -> int:
        return _count_documents_holding_item(
            self.session, SaleItemModel, SaleItemModel.sale_id, item_type, item_id
        )

    def count_by_customer(self, customer_id: int) -> int:
        stmt = select(func.count(SaleModel.id)).where(SaleModel.customer_id == customer_id)
        return int(self.session.execute(stmt).scalar_one())


############################################################
############### Purhcase Payment Repository ################
############################################################
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

    def sum_by_purchase_id(self, purchase_id: int) -> Decimal:
        stmt = select(func.coalesce(func.sum(PurchasePaymentModel.amount), 0)).where(
            PurchasePaymentModel.purchase_id == purchase_id
        )
        total = self.session.execute(stmt).scalar_one()
        return Decimal(total)


############################################################
################### Sale Payment Repository ################
############################################################
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

    def sum_by_sale_id(self, sale_id: int) -> Decimal:
        stmt = select(func.coalesce(func.sum(SalePaymentModel.amount), 0)).where(
            SalePaymentModel.sale_id == sale_id
        )
        total = self.session.execute(stmt).scalar_one()
        return Decimal(total)


############################################################
############## Inventory Movement Repository ###############
############################################################
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

    def list_by_card_id(self, card_id: int, limit: int = 200) -> list[InventoryMovement]:
        stmt = (
            select(InventoryMovementModel)
            .where(InventoryMovementModel.card_id == card_id)
            .order_by(InventoryMovementModel.occurred_at.desc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [InventoryMovementMapper.to_entity(model) for model in models]

    def list_by_inventory_item_id(self, inventory_item_id: int, limit: int = 200) -> list[InventoryMovement]:
        stmt = (
            select(InventoryMovementModel)
            .where(InventoryMovementModel.inventory_item_id == inventory_item_id)
            .order_by(InventoryMovementModel.occurred_at.desc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [InventoryMovementMapper.to_entity(model) for model in models]