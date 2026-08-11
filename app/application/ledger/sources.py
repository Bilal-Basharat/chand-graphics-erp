"""
Where this build's ledgers get their events.

Four small pieces, and they are the *only* code that knows a customer
ledger is made of sales and a supplier ledger of purchases. Adding a
document family — job orders in the other build of this app — means one
more `LedgerSource` here and one line in the container. Nothing above
this file changes.

Each source answers with two queries for the window and one aggregate for
everything before it, so a ledger costs a fixed handful of queries however
long the party's history is.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.application.ledger.ports import (
    LedgerDirection,
    LedgerEvent,
    LedgerParty,
    LedgerSource,
    PartyLookup,
)
from app.application.use_cases.base import UseCase
from app.domain.uow import UnitOfWork

SALE = "sale"
PURCHASE = "purchase"
"""What each source calls the documents it reads.

Every line a source produces is tagged with one of these, which is what
lets a screen open the document behind a line without knowing which
ledger it is drawing. A new family arrives as a new word here, set by the
source that owns it.
"""

_CASH = "Cash"
"""What a payment that names no method was settled with.

The same default the payment screens apply — see
`presentation.formatting.CASH` for why an empty method means cash rather
than missing data.
"""

_METHOD_LIMIT = 500
"""Payment methods are a short hand-kept list; this is a ceiling, not a
page size."""


def _party(record, party_id: int) -> LedgerParty | None:
    """A customer or a supplier as the ledger sees it.

    Both carry the same three facts under the same names, so one function
    serves both and neither entity type is named above this module.
    """
    if record is None:
        return None
    return LedgerParty(
        id=party_id,
        name=record.name,
        opening_balance=record.opening_balance,
    )


class CustomerLookup(PartyLookup):
    def find(self, uow: UnitOfWork, party_id: int) -> LedgerParty | None:
        customers = UseCase.require(uow.customers, "customers")
        return _party(customers.get_by_id(party_id), party_id)


class SupplierLookup(PartyLookup):
    def find(self, uow: UnitOfWork, party_id: int) -> LedgerParty | None:
        suppliers = UseCase.require(uow.suppliers, "suppliers")
        return _party(suppliers.get_by_id(party_id), party_id)


def _method_names(uow: UnitOfWork) -> dict[int, str]:
    """Every payment method, once, so naming N payments costs one query."""
    methods = UseCase.require(uow.payment_methods, "payment_methods")
    return {
        method.id: method.name
        for method in methods.list(limit=_METHOD_LIMIT)
        if method.id is not None
    }


def _settled_with(label: str, methods: dict[int, str], method_id: int | None) -> str:
    """"Payment received · Cash" — what happened, and how.

    A method that is missing reads as cash whether none was chosen or the
    one that was has since been deleted. Neither is missing data.
    """
    return f"{label} · {methods.get(method_id, _CASH)}"


class SaleLedgerSource(LedgerSource):
    """Invoices raised on a customer, and the money received against them."""

    def net_before(self, uow: UnitOfWork, party_id: int, before: datetime) -> Decimal:
        sales = UseCase.require(uow.sales, "sales")
        payments = UseCase.require(uow.sale_payments, "sale_payments")
        return sales.total_by_customer(party_id, before) - payments.total_by_customer(
            party_id, before
        )

    def events(
        self,
        uow: UnitOfWork,
        party_id: int,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[LedgerEvent]:
        sales = UseCase.require(uow.sales, "sales")
        payments = UseCase.require(uow.sale_payments, "sale_payments")

        events = [
            LedgerEvent(
                occurred_at=sale.created_at,
                reference=sale.invoice_no,
                document_kind=SALE,
                detail="Sale",
                amount=sale.grand_total,
                direction=LedgerDirection.CHARGE,
            )
            for sale in sales.list_by_customer(party_id, start, end, limit)
        ]

        received = payments.list_by_customer(party_id, start, end, limit)
        # The invoice a receipt settles may be older than the window, so
        # its number is fetched rather than taken from the sales above.
        invoice_numbers = sales.numbers_by_id({payment.sale_id for payment in received})
        methods = _method_names(uow) if received else {}
        events.extend(
            LedgerEvent(
                occurred_at=payment.received_at,
                reference=invoice_numbers.get(payment.sale_id, ""),
                document_kind=SALE,
                detail=_settled_with("Payment received", methods, payment.payment_method_id),
                amount=payment.amount,
                direction=LedgerDirection.PAYMENT,
            )
            for payment in received
        )
        return events


class PurchaseLedgerSource(LedgerSource):
    """Bills a supplier raised on you, and the money paid against them."""

    def net_before(self, uow: UnitOfWork, party_id: int, before: datetime) -> Decimal:
        purchases = UseCase.require(uow.purchases, "purchases")
        payments = UseCase.require(uow.purchase_payments, "purchase_payments")
        return purchases.total_by_supplier(party_id, before) - payments.total_by_supplier(
            party_id, before
        )

    def events(
        self,
        uow: UnitOfWork,
        party_id: int,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[LedgerEvent]:
        purchases = UseCase.require(uow.purchases, "purchases")
        payments = UseCase.require(uow.purchase_payments, "purchase_payments")

        events = [
            LedgerEvent(
                occurred_at=purchase.created_at,
                reference=purchase.purchase_no,
                document_kind=PURCHASE,
                detail="Purchase",
                amount=purchase.grand_total,
                direction=LedgerDirection.CHARGE,
            )
            for purchase in purchases.list_by_supplier(party_id, start, end, limit)
        ]

        paid = payments.list_by_supplier(party_id, start, end, limit)
        purchase_numbers = purchases.numbers_by_id({payment.purchase_id for payment in paid})
        methods = _method_names(uow) if paid else {}
        events.extend(
            LedgerEvent(
                occurred_at=payment.paid_at,
                reference=purchase_numbers.get(payment.purchase_id, ""),
                document_kind=PURCHASE,
                detail=_settled_with("Payment made", methods, payment.payment_method_id),
                amount=payment.amount,
                direction=LedgerDirection.PAYMENT,
            )
            for payment in paid
        )
        return events
