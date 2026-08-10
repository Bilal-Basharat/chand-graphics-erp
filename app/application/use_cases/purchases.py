from __future__ import annotations

from decimal import Decimal

from app.application.dto.commands import (
    CreatePurchaseCommand,
    DateRangeQuery,
    RecordPurchasePaymentCommand,
)
from app.application.dto.queries import PurchasePaymentStatus
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.stock_helpers import (
    ResolvedStockTarget,
    increase_stock,
    load_stock_target,
)
from app.domain.entities.purchase import Purchase
from app.domain.entities.purchase_item import PurchaseItem
from app.domain.entities.purchase_payment import PurchasePayment
from app.domain.uow import UnitOfWork
from app.domain.enums.item_type import ItemType


from app.application.auth.session import CurrentUserSession
from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import AuthorizedUseCase

class CreatePurchaseUseCase(AuthorizedUseCase[CreatePurchaseCommand, Purchase]):
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

    def execute(self, request: CreatePurchaseCommand) -> Purchase:
        self.require_permission(Permission.MANAGE_PURCHASES)

        if not request.items:
            raise ValueError("purchase must contain at least one item")

        current_user_id = self.current_user_id()
        
        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            suppliers = self.require(uow.suppliers, "suppliers")
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            users = self.require(uow.users, "users")

            if request.supplier_id is not None and suppliers.get_by_id(request.supplier_id) is None:
                raise NotFoundError(f"Supplier id={request.supplier_id} not found")

            # Same reasoning as CreateSaleUseCase: the unique index would
            # refuse this too, but as an unreadable driver error.
            purchase_no = request.purchase_no.strip()
            if purchases.get_by_purchase_no(purchase_no) is not None:
                raise DuplicateEntityError(f"Purchase '{purchase_no}' already exists.")

            purchase = Purchase(
                purchase_no=request.purchase_no.strip(),
                supplier_id=request.supplier_id,
                reference_no=request.reference_no,
                note=request.note,
                discount_amount=request.discount_amount,
                created_by_user_id=current_user_id,
            )

            # See CreateSaleUseCase: one record per item, so two lines for
            # the same item build on one running count.
            targets: dict[tuple[ItemType, int | None], ResolvedStockTarget] = {}

            for item in request.items:
                key = (item.item_type, item.inventory_item_id)
                target = targets.get(key)
                if target is None:
                    target = load_stock_target(uow, item.item_type, item.inventory_item_id)
                    targets[key] = target

                previous_stock, resulting_stock = increase_stock(target.entity, item.quantity)
                target.entity = target.repository.update(target.entity)

                purchase.add_item(
                    PurchaseItem(
                        item_type=item.item_type,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        inventory_item_id=item.inventory_item_id,
                        previous_stock=previous_stock,
                        resulting_stock=resulting_stock,
                        note=item.note,
                    )
                )

            for payment in request.payments:
                # Optional — see CreateSaleUseCase.
                if (
                    payment.payment_method_id is not None
                    and payment_methods.get_by_id(payment.payment_method_id) is None
                ):
                    raise NotFoundError(f"Payment method id={payment.payment_method_id} not found")
                if users.get_by_id(payment.paid_by_user_id) is None:
                    raise NotFoundError(f"User id={payment.paid_by_user_id} not found")

                purchase.add_payment(
                    PurchasePayment(
                        amount=payment.amount,
                        payment_method_id=payment.payment_method_id,
                        paid_by_user_id=payment.paid_by_user_id,
                        reference_no=payment.reference_no,
                        note=payment.note,
                    )
                )

            if purchase.paid_amount > purchase.grand_total:
                raise ValueError("paid amount cannot exceed grand total")

            return purchases.add(purchase)


class RecordPurchasePaymentUseCase(AuthorizedUseCase[RecordPurchasePaymentCommand, Purchase]):
    """
    Record a payment against an existing purchase (partial/credit collection).
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

    def execute(self, request: RecordPurchasePaymentCommand) -> Purchase:
        self.require_permission(Permission.MANAGE_PURCHASES)

        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            payment_methods = self.require(uow.payment_methods, "payment_methods")
            users = self.require(uow.users, "users")

            purchase = purchases.get_by_id(request.purchase_id)
            if purchase is None:
                raise NotFoundError(f"Purchase id={request.purchase_id} not found")

            if (
                request.payment_method_id is not None
                and payment_methods.get_by_id(request.payment_method_id) is None
            ):
                raise NotFoundError(f"Payment method id={request.payment_method_id} not found")

            if users.get_by_id(request.paid_by_user_id) is None:
                raise NotFoundError(f"User id={request.paid_by_user_id} not found")

            if request.amount > purchase.balance_amount:
                raise ValueError("payment amount cannot exceed outstanding balance")

            purchase.add_payment(
                PurchasePayment(
                    amount=request.amount,
                    payment_method_id=request.payment_method_id,
                    paid_by_user_id=request.paid_by_user_id,
                    reference_no=request.reference_no,
                    note=request.note,
                )
            )

            return purchases.update(purchase)


class GetPurchasePaymentStatusUseCase(AuthenticatedUseCase[int, PurchasePaymentStatus]):
    """
    Paid amount and remaining balance for a purchase, computed from the
    actual payment rows recorded against it (supports partial/installment payments).
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int) -> PurchasePaymentStatus:
        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            purchase_payments = self.require(uow.purchase_payments, "purchase_payments")

            purchase = purchases.get_by_id(request)
            if purchase is None:
                raise NotFoundError(f"Purchase id={request} not found")

            paid_amount = purchase_payments.sum_by_purchase_id(request)
            return PurchasePaymentStatus(
                purchase_id=request,
                grand_total=purchase.grand_total,
                paid_amount=paid_amount,
                balance_amount=purchase.grand_total - paid_amount,
            )


class GetPurchaseByNoUseCase(AuthenticatedUseCase[str, Purchase | None]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> Purchase | None:
        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            return purchases.get_by_purchase_no(request.strip())


class ListPurchasesByDateRangeUseCase(AuthenticatedUseCase[DateRangeQuery, list[Purchase]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: DateRangeQuery) -> list[Purchase]:
        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            return purchases.list_by_date_range(request.start, request.end, request.limit)


class GetSupplierPurchaseTotalUseCase(AuthenticatedUseCase[int, Decimal]):
    """
    Total value of all purchases recorded from a given supplier.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int) -> Decimal:
        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            return purchases.sum_by_supplier(request)
