"""
Where this build's ledgers get their events.

Four small pieces, and they are the *only* code that knows a customer
ledger is made of sales and a supplier ledger of purchases. Adding a
document family — job orders in the other build of this app — means one
more `LedgerSource` here and one line in the container. Nothing above
this file changes.

Each source answers with three queries for the window and one aggregate
for everything before it, so a ledger costs a fixed handful of queries
however long the party's history is.
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
SALE_RETURN = "sale_return"
PURCHASE_RETURN = "purchase_return"
"""What each source calls the documents it reads.

Every line a source produces is tagged with one of these, which is what
lets a screen open the document behind a line without knowing which
ledger it is drawing. A new family arrives as a new word here, set by the
source that owns it.

A return is its own kind rather than another sale line, so a statement
can say plainly which entries were goods coming back — and so the screen
can open the invoice they came off.
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


def _return_events(
    returns,
    numbers: dict[int, str],
    document_id_of,
    methods: dict[int, str],
    kind: str,
    goods_detail: str,
    refund_label: str,
    goods_direction: LedgerDirection,
) -> list[LedgerEvent]:
    """One return, said as the one or two things that actually happened.

    Goods coming back and money going back are separate facts and move a
    balance opposite ways, so they are separate lines. A return with no
    refund leaves the party in credit, which is the truth of it — the
    value is theirs to spend against the next document.

    Written once because a customer's return and a supplier's differ only
    in which direction each half points, which the caller passes in.
    """
    refund_direction = (
        LedgerDirection.CHARGE
        if goods_direction is LedgerDirection.PAYMENT
        else LedgerDirection.PAYMENT
    )

    events: list[LedgerEvent] = []
    for record in returns:
        reference = numbers.get(document_id_of(record), record.return_no)
        events.append(
            LedgerEvent(
                occurred_at=record.returned_at,
                reference=reference,
                document_kind=kind,
                detail=f"{goods_detail} · {record.return_no}",
                amount=record.return_amount,
                direction=goods_direction,
            )
        )
        if record.refund_amount > 0:
            events.append(
                LedgerEvent(
                    occurred_at=record.returned_at,
                    reference=reference,
                    document_kind=kind,
                    detail=_settled_with(refund_label, methods, record.refund_method_id),
                    amount=record.refund_amount,
                    direction=refund_direction,
                )
            )
    return events


class SaleLedgerSource(LedgerSource):
    """Invoices raised on a customer, the money received against them, and
    anything that came back."""

    def net_before(self, uow: UnitOfWork, party_id: int, before: datetime) -> Decimal:
        sales = UseCase.require(uow.sales, "sales")
        payments = UseCase.require(uow.sale_payments, "sale_payments")
        returns = UseCase.require(uow.sale_returns, "sale_returns")
        # Charges, less what was paid, less the value of what came back,
        # plus any refund handed over — the same four figures the lines
        # below produce, so the opening balance agrees with them.
        return (
            sales.total_by_customer(party_id, before)
            - payments.total_by_customer(party_id, before)
            - returns.credit_before(party_id, before)
            + returns.refund_before(party_id, before)
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

        # The invoice a return came off may be older than the window, so
        # its number is fetched the same way a receipt's is.
        returned = UseCase.require(uow.sale_returns, "sale_returns").list_by_customer(
            party_id, start, end, limit
        )
        if returned:
            events.extend(
                _return_events(
                    returned,
                    sales.numbers_by_id({record.sale_id for record in returned}),
                    lambda record: record.sale_id,
                    methods or _method_names(uow),
                    SALE_RETURN,
                    "Goods returned",
                    "Refund paid",
                    # Goods back reduce what the customer owes; the refund
                    # that may follow puts it back up again.
                    LedgerDirection.PAYMENT,
                )
            )
        return events


class PurchaseLedgerSource(LedgerSource):
    """Bills a supplier raised on you, and the money paid against them."""

    def net_before(self, uow: UnitOfWork, party_id: int, before: datetime) -> Decimal:
        purchases = UseCase.require(uow.purchases, "purchases")
        payments = UseCase.require(uow.purchase_payments, "purchase_payments")
        returns = UseCase.require(uow.purchase_returns, "purchase_returns")
        return (
            purchases.total_by_supplier(party_id, before)
            - payments.total_by_supplier(party_id, before)
            - returns.credit_before(party_id, before)
            + returns.refund_before(party_id, before)
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

        returned = UseCase.require(uow.purchase_returns, "purchase_returns").list_by_supplier(
            party_id, start, end, limit
        )
        if returned:
            events.extend(
                _return_events(
                    returned,
                    purchases.numbers_by_id({record.purchase_id for record in returned}),
                    lambda record: record.purchase_id,
                    methods or _method_names(uow),
                    PURCHASE_RETURN,
                    "Goods sent back",
                    "Refund received",
                    # Goods back reduce what is owed to the supplier; a
                    # refund they hand over puts it back up again.
                    LedgerDirection.PAYMENT,
                )
            )
        return events
