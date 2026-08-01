from __future__ import annotations

from app.application.dto.commands import (
    CreateSaleCommand,
    DateRangeQuery,
    RecordSalePaymentCommand,
    SaleItemCommand,
    SalePaymentCommand,
)
from app.application.dto.queries import SalePaymentStatus
from app.application.exceptions import NotFoundError
from app.application.use_cases.base import UseCase
from app.application.use_cases.stock_helpers import decrease_stock, increase_stock, load_stock_target
from app.domain.entities.sale import Sale
from app.domain.entities.sale_item import SaleItem
from app.domain.entities.sale_payment import SalePayment
from app.domain.uow import UnitOfWork

from app.domain.enums.item_type import ItemType

from app.application.auth.session import CurrentUserSession
from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import AuthorizedUseCase

class CreateSaleUseCase(AuthorizedUseCase[CreateSaleCommand, Sale]):
    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreateSaleCommand) -> Sale:
        self.require_permission(Permission.MANAGE_SALES)

        if not request.items:
            raise ValueError("sale must contain at least one item")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            customers = self.require(uow.customers, "customers")
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            users = self.require(uow.users, "users")

            if request.customer_id is not None and customers.get_by_id(request.customer_id) is None:
                raise NotFoundError(f"Customer id={request.customer_id} not found")

            sale = Sale(
                invoice_no=request.invoice_no.strip(),
                customer_id=request.customer_id,
                note=request.note,
                discount_amount=request.discount_amount,
                created_by_user_id=current_user_id,
            )

            stock_cache: dict[tuple[str, int], object] = {}

            for item in request.items:
                if item.item_type == ItemType.CARD:
                    if item.card_id is None:
                        raise ValueError("card_id is required for CARD items")
                    key = ("CARD", item.card_id)
                    if key not in stock_cache:
                        stock_cache[key] = self.require(uow.cards, "cards").get_by_id(item.card_id)
                        if stock_cache[key] is None:
                            raise NotFoundError(f"Card id={item.card_id} not found")
                    card = stock_cache[key]
                    previous_stock, resulting_stock = decrease_stock(card, item.quantity)
                    stock_cache[key] = self.require(uow.cards, "cards").update(card)
                else:
                    if item.inventory_item_id is None:
                        raise ValueError("inventory_item_id is required for INVENTORY_ITEM items")
                    key = ("ITEM", item.inventory_item_id)
                    if key not in stock_cache:
                        stock_cache[key] = self.require(uow.inventory_items, "inventory_items").get_by_id(item.inventory_item_id)
                        if stock_cache[key] is None:
                            raise NotFoundError(f"Inventory item id={item.inventory_item_id} not found")
                    inv_item = stock_cache[key]
                    previous_stock, resulting_stock = decrease_stock(inv_item, item.quantity)
                    stock_cache[key] = self.require(uow.inventory_items, "inventory_items").update(inv_item)

                sale.add_item(
                    SaleItem(
                        item_type=item.item_type,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        card_id=item.card_id,
                        inventory_item_id=item.inventory_item_id,
                        previous_stock=previous_stock,
                        resulting_stock=resulting_stock,
                        note=item.note,
                    )
                )

            for payment in request.payments:
                if payment_methods.get_by_id(payment.payment_method_id) is None:
                    raise NotFoundError(f"Payment method id={payment.payment_method_id} not found")
                if users.get_by_id(payment.received_by_user_id) is None:
                    raise NotFoundError(f"User id={payment.received_by_user_id} not found")

                sale.add_payment(
                    SalePayment(
                        amount=payment.amount,
                        payment_method_id=payment.payment_method_id,
                        received_by_user_id=payment.received_by_user_id,
                        reference_no=payment.reference_no,
                        note=payment.note,
                    )
                )

            if sale.paid_amount > sale.grand_total:
                raise ValueError("paid amount cannot exceed grand total")

            return sales.add(sale)


class RecordSalePaymentUseCase(AuthorizedUseCase[RecordSalePaymentCommand, Sale]):
    """
    Record a payment against an existing sale (partial/credit collection).
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: RecordSalePaymentCommand) -> Sale:
        self.require_permission(Permission.MANAGE_SALES)

        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            users = self.require(uow.users, "users")

            sale = sales.get_by_id(request.sale_id)
            if sale is None:
                raise NotFoundError(f"Sale id={request.sale_id} not found")

            if payment_methods.get_by_id(request.payment_method_id) is None:
                raise NotFoundError(f"Payment method id={request.payment_method_id} not found")

            if users.get_by_id(request.received_by_user_id) is None:
                raise NotFoundError(f"User id={request.received_by_user_id} not found")

            if request.amount > sale.balance_amount:
                raise ValueError("payment amount cannot exceed outstanding balance")

            sale.add_payment(
                SalePayment(
                    amount=request.amount,
                    payment_method_id=request.payment_method_id,
                    received_by_user_id=request.received_by_user_id,
                    reference_no=request.reference_no,
                    note=request.note,
                )
            )

            return sales.update(sale)


class GetSalePaymentStatusUseCase(AuthenticatedUseCase[int, SalePaymentStatus]):
    """
    Paid amount and remaining balance for a sale, computed from the
    actual payment rows recorded against it (supports partial/installment payments).
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int) -> SalePaymentStatus:
        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            sale_payments = self.require(uow.sale_payments, "sale_payments")

            sale = sales.get_by_id(request)
            if sale is None:
                raise NotFoundError(f"Sale id={request} not found")

            paid_amount = sale_payments.sum_by_sale_id(request)
            return SalePaymentStatus(
                sale_id=request,
                grand_total=sale.grand_total,
                paid_amount=paid_amount,
                balance_amount=sale.grand_total - paid_amount,
            )


class GetSaleByInvoiceNoUseCase(AuthenticatedUseCase[str, Sale | None]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> Sale | None:
        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            return sales.get_by_invoice_no(request.strip())


class ListSalesByDateRangeUseCase(AuthenticatedUseCase[DateRangeQuery, list[Sale]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: DateRangeQuery) -> list[Sale]:
        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            return sales.list_by_date_range(request.start, request.end, request.limit)