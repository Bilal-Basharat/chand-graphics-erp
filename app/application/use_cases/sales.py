from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import (
    CreateSaleCommand,
    DateRangeQuery,
    RecordSalePaymentCommand,
)
from app.application.dto.queries import SalePaymentStatus
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.stock_helpers import (
    ResolvedStockTarget,
    decrease_stock,
    load_stock_target,
)
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
            purchases = self.require(uow.purchases, "purchases")

            if request.customer_id is not None and customers.get_by_id(request.customer_id) is None:
                raise NotFoundError(f"Customer id={request.customer_id} not found")

            # Checked here rather than left to the unique index: the index
            # refuses too, but as a driver error the UI can only report as
            # "something went wrong". The number is editable on the form,
            # so colliding with an existing document is an ordinary
            # mistake deserving an ordinary message.
            invoice_no = request.invoice_no.strip()
            if sales.get_by_invoice_no(invoice_no) is not None:
                raise DuplicateEntityError(f"Invoice '{invoice_no}' already exists.")

            sale = Sale(
                invoice_no=request.invoice_no.strip(),
                customer_id=request.customer_id,
                note=request.note,
                discount_amount=request.discount_amount,
                created_by_user_id=current_user_id,
            )

            # One record per item on the invoice, so a second line for the
            # same item draws down the running count rather than starting
            # again from what was on the shelf when the sale began.
            targets: dict[tuple[ItemType, int | None], ResolvedStockTarget] = {}
            # ...and one cost lookup per item, for the same reason: two
            # lines of the same thing on one invoice cost the same.
            costs: dict[tuple[ItemType, int | None], Decimal | None] = {}

            for item in request.items:
                key = (item.item_type, item.inventory_item_id)
                target = targets.get(key)
                if target is None:
                    target = load_stock_target(uow, item.item_type, item.inventory_item_id)
                    targets[key] = target
                if key not in costs:
                    # Recorded on the line rather than looked up when a
                    # report is run: buying this item again next month must
                    # not rewrite the margin on an invoice already handed
                    # over. None when it has never been bought — see
                    # `SaleItem.unit_cost`.
                    costs[key] = purchases.weighted_average_cost(
                        item.item_type, item.inventory_item_id
                    )

                if target.entity.is_low_stock:
                    raise ValueError(
                        f"'{target.entity.name}' is low/out of stock and cannot be sold."
                    )

                previous_stock, resulting_stock = decrease_stock(target.entity, item.quantity)
                target.entity = target.repository.update(target.entity)

                sale.add_item(
                    SaleItem(
                        item_type=item.item_type,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        unit_cost=costs[key],
                        inventory_item_id=item.inventory_item_id,
                        previous_stock=previous_stock,
                        resulting_stock=resulting_stock,
                        note=item.note,
                    )
                )

            for payment in request.payments:
                # Optional: a payment with no method named is cash over the
                # counter, which is most of them.
                if (
                    payment.payment_method_id is not None
                    and payment_methods.get_by_id(payment.payment_method_id) is None
                ):
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

            if (
                request.payment_method_id is not None
                and payment_methods.get_by_id(request.payment_method_id) is None
            ):
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