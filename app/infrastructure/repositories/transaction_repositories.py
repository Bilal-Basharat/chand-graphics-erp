from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.entities.expense import Expense
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.entities.purchase import Purchase
from app.domain.entities.purchase_payment import PurchasePayment
from app.domain.entities.sale import Sale
from app.domain.entities.sale_payment import SalePayment
from app.domain.enums.item_type import ItemType
from app.domain.enums.payment_filter import PaymentFilter
from app.domain.repositories.aggregates import (
    CategorySpendRow,
    CostTotals,
    ItemMarginRow,
    OutstandingRow,
    RevenueTotals,
)
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
from app.infrastructure.db.models.expense_category_model import ExpenseCategoryModel
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
from app.infrastructure.repositories.paging import contains, matching, totals


_PAISA = Decimal("0.01")
"""What money rounds to here, matching `presentation.formatting.money`."""


def _money(value) -> Decimal:
    """A driver's answer as an amount of money.

    SQLite hands back a float rather than a numeric whenever an aggregate
    mixes a column with a literal — which every CASE below does — and
    `Decimal(0.05)` is not 0.05 but forty digits of binary approximation.
    Rounding it here is what stops that reaching a total on screen.
    """
    return Decimal(value).quantize(_PAISA, rounding=ROUND_HALF_UP)


def _item_column(line_model, item_type: ItemType):
    """The foreign key a line of `item_type` carries.

    The one place a line's item type turns into a column. A special item
    module adds its column to this mapping, and every query below reaches
    it without a branch of its own.
    """
    columns = {ItemType.INVENTORY_ITEM: line_model.inventory_item_id}
    try:
        return columns[item_type]
    except KeyError:
        raise ValueError(f"Unsupported item type: {item_type}") from None


def _count_documents_holding_item(
    session: Session,
    line_model,
    document_column,
    item_type: ItemType,
    item_id: int,
) -> int:
    """How many documents have a line pointing at one catalogue item.

    Sale lines and purchase lines are the same shape, so the query is
    written once. Documents rather than lines: an item listed twice on one
    invoice is still one invoice standing in the way of deleting it.
    """
    stmt = select(func.count(func.distinct(document_column))).where(
        _item_column(line_model, item_type) == item_id
    )
    return int(session.execute(stmt).scalar_one())


def _paid_as(model, payment: str | None):
    """How far paid, as a condition on a document's stored figures.

    Written against `grand_total` and `balance_amount` — the columns the
    document was saved with — because a page of a thousand rows cannot ask
    each entity to add its own lines up. `Sale` and `Purchase` compute the
    same two figures from their lines, and the mapper writes them back on
    every save, so the list and the document agree.

    None means "every document": the absence of a filter, not a filter
    that matches nothing.
    """
    if payment == PaymentFilter.NOT_FULLY_PAID:
        return model.balance_amount > 0
    if payment == PaymentFilter.NOTHING_PAID:
        return model.balance_amount >= model.grand_total
    if payment == PaymentFilter.PART_PAID:
        return (model.balance_amount > 0) & (model.balance_amount < model.grand_total)
    if payment == PaymentFilter.FULLY_PAID:
        return model.balance_amount <= 0
    return None


def _sum_of(model):
    """What a document list adds up to: what it came to, and what is left
    owing on it."""
    return (
        func.coalesce(func.sum(model.grand_total), 0),
        func.coalesce(func.sum(model.balance_amount), 0),
    )


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

    _SORTABLE = {
        "name": ExpenseModel.expense_name,
        "created": ExpenseModel.created_at,
        "amount": ExpenseModel.total_amount,
        "category": ExpenseCategoryModel.name,
    }

    def _filtered_expenses(
        self,
        start: datetime,
        end: datetime,
        search: str,
        category_id: int | None,
        uncategorised: bool,
    ):
        """The conditions the page, its count and its total all share."""
        stmt = (
            select(ExpenseModel)
            # Always joined, not only when searching: the list can be
            # ordered by category, and an order needs the column present.
            .outerjoin(ExpenseCategoryModel, ExpenseModel.category_id == ExpenseCategoryModel.id)
            .where(ExpenseModel.created_at >= start)
            .where(ExpenseModel.created_at <= end)
        )
        if search:
            stmt = stmt.where(
                matching(
                    contains(search),
                    ExpenseModel.expense_name,
                    ExpenseModel.remarks,
                    ExpenseCategoryModel.name,
                )
            )
        if uncategorised:
            # Its own condition rather than a category id of None, which
            # already means "every category".
            stmt = stmt.where(ExpenseModel.category_id.is_(None))
        elif category_id is not None:
            stmt = stmt.where(ExpenseModel.category_id == category_id)
        return stmt

    def page_expenses(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        category_id: int | None = None,
        uncategorised: bool = False,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Expense]:
        return self.page_of(
            self._filtered_expenses(start, end, search, category_id, uncategorised),
            sortable=self._SORTABLE,
            default_sort="created",
            default_desc=True,
            sort_field=sort_field,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

    def count_expenses(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        category_id: int | None = None,
        uncategorised: bool = False,
    ) -> int:
        return self.count_of(
            self._filtered_expenses(start, end, search, category_id, uncategorised)
        )

    def sum_expenses(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        category_id: int | None = None,
        uncategorised: bool = False,
    ) -> Decimal:
        """What the whole filtered period comes to, not this page of it."""
        spent = totals(
            self.session,
            self._filtered_expenses(start, end, search, category_id, uncategorised),
            func.coalesce(func.sum(ExpenseModel.total_amount), 0),
        )[0]
        return _money(spent)

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

    def total_by_category_between(
        self, start: datetime, end: datetime
    ) -> list[CategorySpendRow]:
        """What was spent in a period, grouped by category.

        No limit: a report that answers about the first few hundred
        expenses is not a report. One row per category is a handful of
        rows however many expenses are behind them.
        """
        stmt = (
            select(
                ExpenseModel.category_id,
                func.count(ExpenseModel.id),
                func.coalesce(func.sum(ExpenseModel.total_amount), 0),
            )
            .where(ExpenseModel.created_at >= start, ExpenseModel.created_at <= end)
            .group_by(ExpenseModel.category_id)
        )
        return [
            # A null category is spending nobody filed — a real group, not
            # a missing one.
            CategorySpendRow(category_id=category_id, count=int(count), total=_money(total))
            for category_id, count, total in self.session.execute(stmt)
        ]


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

    _SORTABLE = {
        "number": PurchaseModel.purchase_no,
        "supplier": SupplierModel.name,
        "created": PurchaseModel.created_at,
        "total": PurchaseModel.grand_total,
        "balance": PurchaseModel.balance_amount,
        "reference": PurchaseModel.reference_no,
    }

    def _filtered_purchases(
        self,
        start: datetime,
        end: datetime,
        search: str,
        payment: str | None,
    ):
        stmt = (
            select(PurchaseModel)
            .outerjoin(SupplierModel, PurchaseModel.supplier_id == SupplierModel.id)
            .where(PurchaseModel.created_at >= start)
            .where(PurchaseModel.created_at <= end)
        )
        if search:
            stmt = stmt.where(
                matching(
                    contains(search),
                    PurchaseModel.purchase_no,
                    SupplierModel.name,
                    PurchaseModel.reference_no,
                    PurchaseModel.note,
                )
            )
        paid = _paid_as(PurchaseModel, payment)
        if paid is not None:
            stmt = stmt.where(paid)
        return stmt

    def page_purchases(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Purchase]:
        return self.page_of(
            self._filtered_purchases(start, end, search, payment).options(
                # `Purchase` totals itself from its lines, so they travel
                # with the header or every row on the page reads 0.00.
                selectinload(PurchaseModel.items),
                selectinload(PurchaseModel.payments),
            ),
            sortable=self._SORTABLE,
            default_sort="created",
            default_desc=True,
            sort_field=sort_field,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

    def count_purchases(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
    ) -> int:
        return self.count_of(self._filtered_purchases(start, end, search, payment))

    def sum_purchases(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
    ) -> tuple[Decimal, Decimal]:
        """What the filtered period came to, and what is still owed on it."""
        total, outstanding = totals(
            self.session,
            self._filtered_purchases(start, end, search, payment),
            *_sum_of(PurchaseModel),
        )
        return _money(total), _money(outstanding)

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

    def weighted_average_cost(self, item_type: ItemType, item_id: int) -> Decimal | None:
        """What one of these has cost, averaged over everything bought so far.

        Weighted by quantity, not a plain average of prices: a hundred
        sheets at 10 and one at 100 cost about 10 each, not 55.

        Returns None when the item has never been bought. That is not
        zero, and callers must not fold it into a total as if it were.
        """
        stmt = select(
            func.sum(PurchaseItemModel.line_total),
            func.sum(PurchaseItemModel.quantity),
        ).where(
            _item_column(PurchaseItemModel, item_type) == item_id,
            PurchaseItemModel.quantity > 0,
        )
        total, quantity = self.session.execute(stmt).one()
        if not quantity:
            return None
        # Quantized here, and the same way the migration's backfill rounds,
        # so a line written today and one reconstructed by the migration
        # cannot disagree in the last paisa.
        return (Decimal(total) / Decimal(quantity)).quantize(_PAISA, rounding=ROUND_HALF_UP)

    def list_by_supplier(
        self,
        supplier_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[Purchase]:
        stmt = (
            select(PurchaseModel)
            .where(PurchaseModel.supplier_id == supplier_id)
            .where(PurchaseModel.created_at >= start)
            .where(PurchaseModel.created_at <= end)
            .order_by(PurchaseModel.created_at.asc())
            # `Purchase.grand_total` is computed from the lines, so they
            # have to travel with the header or every row costs a query.
            .options(
                selectinload(PurchaseModel.items),
                selectinload(PurchaseModel.payments),
            )
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [PurchaseMapper.to_entity(model) for model in models]

    def numbers_by_id(self, purchase_ids: Collection[int]) -> dict[int, str]:
        ids = set(purchase_ids)
        if not ids:
            return {}
        stmt = select(PurchaseModel.id, PurchaseModel.purchase_no).where(PurchaseModel.id.in_(ids))
        return {row.id: row.purchase_no for row in self.session.execute(stmt)}

    def total_by_supplier(self, supplier_id: int, before: datetime) -> Decimal:
        # The stored `grand_total`, not the computed one: this is an
        # aggregate over rows we deliberately do not load. It is written on
        # every save and a purchase is never edited afterwards.
        stmt = select(func.coalesce(func.sum(PurchaseModel.grand_total), 0)).where(
            PurchaseModel.supplier_id == supplier_id,
            PurchaseModel.created_at < before,
        )
        return Decimal(self.session.execute(stmt).scalar_one())

    def count_by_supplier(self, supplier_id: int) -> int:
        stmt = select(func.count(PurchaseModel.id)).where(
            PurchaseModel.supplier_id == supplier_id
        )
        return int(self.session.execute(stmt).scalar_one())

    def spend_between(self, start: datetime, end: datetime) -> Decimal:
        """What was spent on stock in a period.

        Context for a profit and loss, not a cost of one: stock bought and
        not yet sold is money moved, not money gone.
        """
        stmt = select(func.coalesce(func.sum(PurchaseModel.grand_total), 0)).where(
            PurchaseModel.created_at >= start, PurchaseModel.created_at <= end
        )
        return _money(self.session.execute(stmt).scalar_one())

    def outstanding_before(self, as_at: datetime) -> list[OutstandingRow]:
        """Bills with money still on them, oldest first."""
        stmt = (
            select(
                PurchaseModel.purchase_no,
                SupplierModel.name,
                PurchaseModel.created_at,
                PurchaseModel.balance_amount,
            )
            .join(SupplierModel, PurchaseModel.supplier_id == SupplierModel.id, isouter=True)
            .where(
                PurchaseModel.balance_amount > 0,
                PurchaseModel.created_at <= as_at,
            )
            .order_by(PurchaseModel.created_at.asc())
        )
        return [
            OutstandingRow(
                reference=reference,
                party_name=party,
                occurred_at=occurred_at,
                outstanding=_money(outstanding),
            )
            for reference, party, occurred_at, outstanding in self.session.execute(stmt)
        ]


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

    _SORTABLE = {
        "invoice": SaleModel.invoice_no,
        "customer": CustomerModel.name,
        "created": SaleModel.created_at,
        "total": SaleModel.grand_total,
        "balance": SaleModel.balance_amount,
    }

    def _filtered_sales(
        self,
        start: datetime,
        end: datetime,
        search: str,
        payment: str | None,
    ):
        stmt = (
            select(SaleModel)
            .outerjoin(CustomerModel, SaleModel.customer_id == CustomerModel.id)
            .where(SaleModel.created_at >= start)
            .where(SaleModel.created_at <= end)
        )
        if search:
            stmt = stmt.where(
                matching(
                    contains(search),
                    SaleModel.invoice_no,
                    CustomerModel.name,
                    SaleModel.note,
                )
            )
        paid = _paid_as(SaleModel, payment)
        if paid is not None:
            stmt = stmt.where(paid)
        return stmt

    def page_sales(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Sale]:
        return self.page_of(
            self._filtered_sales(start, end, search, payment).options(
                # `Sale` totals itself from its lines, so they travel with
                # the header or every row on the page reads 0.00.
                selectinload(SaleModel.items),
                selectinload(SaleModel.payments),
            ),
            sortable=self._SORTABLE,
            default_sort="created",
            default_desc=True,
            sort_field=sort_field,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

    def count_sales(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
    ) -> int:
        return self.count_of(self._filtered_sales(start, end, search, payment))

    def sum_sales(
        self,
        *,
        start: datetime,
        end: datetime,
        search: str = "",
        payment: str | None = None,
    ) -> tuple[Decimal, Decimal]:
        """What the filtered period sold, and what is still to collect."""
        total, outstanding = totals(
            self.session,
            self._filtered_sales(start, end, search, payment),
            *_sum_of(SaleModel),
        )
        return _money(total), _money(outstanding)

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

    def count_by_item(self, item_type: ItemType, item_id: int) -> int:
        return _count_documents_holding_item(
            self.session, SaleItemModel, SaleItemModel.sale_id, item_type, item_id
        )

    def count_by_customer(self, customer_id: int) -> int:
        stmt = select(func.count(SaleModel.id)).where(SaleModel.customer_id == customer_id)
        return int(self.session.execute(stmt).scalar_one())

    ####################### reporting aggregates #######################
    # None of these takes a limit. A report that answers about the first
    # page of a period is a report that is quietly wrong, which is what
    # the screen these replaced did at two thousand documents.

    def revenue_between(self, start: datetime, end: datetime) -> RevenueTotals:
        """What was invoiced in a period, before and after discounts."""
        stmt = select(
            func.coalesce(func.sum(SaleModel.subtotal), 0),
            func.coalesce(func.sum(SaleModel.discount_amount), 0),
            func.coalesce(func.sum(SaleModel.grand_total), 0),
            func.count(SaleModel.id),
        ).where(SaleModel.created_at >= start, SaleModel.created_at <= end)

        gross, discounts, net, count = self.session.execute(stmt).one()
        return RevenueTotals(
            gross=_money(gross),
            discounts=_money(discounts),
            net=_money(net),
            invoice_count=int(count),
        )

    def cost_of_sales_between(self, start: datetime, end: datetime) -> CostTotals:
        """What the stock sold in a period had cost.

        Lines with no recorded cost are counted and their revenue
        reported, never added in as zero — that would turn "we don't know"
        into "it was free".
        """
        costed = SaleItemModel.unit_cost.is_not(None)
        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (costed, SaleItemModel.unit_cost * SaleItemModel.quantity),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(func.sum(case((costed, 0), else_=1)), 0),
                func.coalesce(
                    func.sum(case((costed, 0), else_=SaleItemModel.line_total)), 0
                ),
            )
            .join(SaleModel, SaleItemModel.sale_id == SaleModel.id)
            .where(SaleModel.created_at >= start, SaleModel.created_at <= end)
        )

        cost, uncosted_lines, uncosted_revenue = self.session.execute(stmt).one()
        return CostTotals(
            cost_of_goods_sold=_money(cost),
            uncosted_lines=int(uncosted_lines),
            uncosted_revenue=_money(uncosted_revenue),
        )

    def margin_by_item_between(self, start: datetime, end: datetime) -> list[ItemMarginRow]:
        """Every item sold in a period, one row each."""
        costed = SaleItemModel.unit_cost.is_not(None)
        stmt = (
            select(
                SaleItemModel.inventory_item_id,
                func.coalesce(func.sum(SaleItemModel.quantity), 0),
                func.coalesce(func.sum(SaleItemModel.line_total), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (costed, SaleItemModel.unit_cost * SaleItemModel.quantity),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(func.sum(case((costed, 0), else_=1)), 0),
            )
            .join(SaleModel, SaleItemModel.sale_id == SaleModel.id)
            .where(SaleModel.created_at >= start, SaleModel.created_at <= end)
            .group_by(SaleItemModel.inventory_item_id)
        )
        return [
            ItemMarginRow(
                item_id=item_id,
                quantity_sold=int(quantity),
                revenue=_money(revenue),
                cost=_money(cost),
                uncosted_lines=int(uncosted),
            )
            for item_id, quantity, revenue, cost, uncosted in self.session.execute(stmt)
        ]

    def outstanding_before(self, as_at: datetime) -> list[OutstandingRow]:
        """Invoices with money still on them, oldest first."""
        stmt = (
            select(
                SaleModel.invoice_no,
                CustomerModel.name,
                SaleModel.created_at,
                SaleModel.balance_amount,
            )
            .join(CustomerModel, SaleModel.customer_id == CustomerModel.id, isouter=True)
            .where(SaleModel.balance_amount > 0, SaleModel.created_at <= as_at)
            .order_by(SaleModel.created_at.asc())
        )
        return [
            OutstandingRow(
                reference=reference,
                party_name=party,
                occurred_at=occurred_at,
                outstanding=_money(outstanding),
            )
            for reference, party, occurred_at, outstanding in self.session.execute(stmt)
        ]

    def list_by_customer(
        self,
        customer_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[Sale]:
        stmt = (
            select(SaleModel)
            .where(SaleModel.customer_id == customer_id)
            .where(SaleModel.created_at >= start)
            .where(SaleModel.created_at <= end)
            .order_by(SaleModel.created_at.asc())
            # `Sale.grand_total` is computed from the lines, so they have
            # to travel with the header or every row costs a query.
            .options(
                selectinload(SaleModel.items),
                selectinload(SaleModel.payments),
            )
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [SaleMapper.to_entity(model) for model in models]

    def numbers_by_id(self, sale_ids: Collection[int]) -> dict[int, str]:
        ids = set(sale_ids)
        if not ids:
            return {}
        stmt = select(SaleModel.id, SaleModel.invoice_no).where(SaleModel.id.in_(ids))
        return {row.id: row.invoice_no for row in self.session.execute(stmt)}

    def total_by_customer(self, customer_id: int, before: datetime) -> Decimal:
        # The stored `grand_total`, not the computed one: this is an
        # aggregate over rows we deliberately do not load. It is written on
        # every save and a sale is never edited afterwards.
        stmt = select(func.coalesce(func.sum(SaleModel.grand_total), 0)).where(
            SaleModel.customer_id == customer_id,
            SaleModel.created_at < before,
        )
        return Decimal(self.session.execute(stmt).scalar_one())


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

    def list_by_supplier(
        self,
        supplier_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[PurchasePayment]:
        # A payment reaches its supplier through the purchase it settles;
        # bounded by when it was paid, not by when that purchase was made.
        stmt = (
            select(PurchasePaymentModel)
            .join(PurchaseModel, PurchasePaymentModel.purchase_id == PurchaseModel.id)
            .where(PurchaseModel.supplier_id == supplier_id)
            .where(PurchasePaymentModel.paid_at >= start)
            .where(PurchasePaymentModel.paid_at <= end)
            .order_by(PurchasePaymentModel.paid_at.asc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [PurchasePaymentMapper.to_entity(model) for model in models]

    def total_by_supplier(self, supplier_id: int, before: datetime) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(PurchasePaymentModel.amount), 0))
            .join(PurchaseModel, PurchasePaymentModel.purchase_id == PurchaseModel.id)
            .where(PurchaseModel.supplier_id == supplier_id)
            .where(PurchasePaymentModel.paid_at < before)
        )
        return Decimal(self.session.execute(stmt).scalar_one())


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

    def list_by_customer(
        self,
        customer_id: int,
        start: datetime,
        end: datetime,
        limit: int = 500,
    ) -> list[SalePayment]:
        # A payment reaches its customer through the sale it settles;
        # bounded by when it was received, not by when that sale was made.
        stmt = (
            select(SalePaymentModel)
            .join(SaleModel, SalePaymentModel.sale_id == SaleModel.id)
            .where(SaleModel.customer_id == customer_id)
            .where(SalePaymentModel.received_at >= start)
            .where(SalePaymentModel.received_at <= end)
            .order_by(SalePaymentModel.received_at.asc())
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [SalePaymentMapper.to_entity(model) for model in models]

    def total_by_customer(self, customer_id: int, before: datetime) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(SalePaymentModel.amount), 0))
            .join(SaleModel, SalePaymentModel.sale_id == SaleModel.id)
            .where(SaleModel.customer_id == customer_id)
            .where(SalePaymentModel.received_at < before)
        )
        return Decimal(self.session.execute(stmt).scalar_one())


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

    _SORTABLE = {
        "occurred": InventoryMovementModel.occurred_at,
        "type": InventoryMovementModel.movement_type,
        "quantity": InventoryMovementModel.quantity,
        "stock": InventoryMovementModel.resulting_stock,
    }

    def _filtered_movements(self, inventory_item_id: int, movement_type: str | None, search: str):
        stmt = select(InventoryMovementModel).where(
            InventoryMovementModel.inventory_item_id == inventory_item_id
        )
        if movement_type:
            stmt = stmt.where(InventoryMovementModel.movement_type == movement_type)
        if search:
            stmt = stmt.where(
                matching(
                    contains(search),
                    InventoryMovementModel.reference_no,
                    InventoryMovementModel.reason,
                    InventoryMovementModel.note,
                )
            )
        return stmt

    def page_movements(
        self,
        *,
        inventory_item_id: int,
        movement_type: str | None = None,
        search: str = "",
        sort_field: str | None = None,
        sort_desc: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[InventoryMovement]:
        return self.page_of(
            self._filtered_movements(inventory_item_id, movement_type, search),
            sortable=self._SORTABLE,
            default_sort="occurred",
            default_desc=True,
            sort_field=sort_field,
            sort_desc=sort_desc,
            limit=limit,
            offset=offset,
        )

    def count_movements(
        self,
        *,
        inventory_item_id: int,
        movement_type: str | None = None,
        search: str = "",
    ) -> int:
        return self.count_of(
            self._filtered_movements(inventory_item_id, movement_type, search)
        )

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

