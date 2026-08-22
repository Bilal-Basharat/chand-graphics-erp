"""
Goods coming back, and the four records that have to agree afterwards.

A return is the one operation in this application that touches stock, a
document, a party's account and the till at once. It is written here as a
single unit of work so those four either all move or none of them do.

Every returned line names the document line it reverses. That is not
bookkeeping tidiness: it is the only thing that can say how much may come
back. An item bought a hundred times and never sold has no sale line to
return against, and so cannot be "returned by a customer" at all — which
is exactly the hole this module closes.

A return carries as many lines as came back together. One trip to the
counter is one return: one number, one movement of money, one line on the
party's account.

Sales and purchases are written out separately rather than through one
generic use case. They differ in permission, in which way stock moves,
in which repository they reach and in what a refund means, which is most
of what either of them does; folding them together would leave a class
made of branches on `is_sale`.
"""
from __future__ import annotations

from decimal import Decimal

from app.application.auth.permissions import Permission
from app.application.dto.commands import (
    RecordPurchaseReturnCommand,
    RecordSaleReturnCommand,
    ReturnedLineCommand,
)
from app.application.dto.queries import (
    ReturnableDocument,
    ReturnableDocumentQuery,
    ReturnableLine,
)
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import AuthorizedUnitOfWorkUseCase
from app.application.use_cases.base import UseCase
from app.application.use_cases.stock_helpers import (
    decrease_stock,
    increase_stock,
    load_stock_target,
    returned_base_quantity,
)
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.entities.purchase_return import PurchaseReturn
from app.domain.entities.purchase_return_item import PurchaseReturnItem
from app.domain.entities.sale_return import SaleReturn
from app.domain.entities.sale_return_item import SaleReturnItem
from app.domain.enums.movement_type import MovementType
from app.domain.quantities import to_quantity
from app.domain.uow import UnitOfWork
from app.shared.datetimes import now_pkt

SALE_RETURN = "SALE_RETURN"
PURCHASE_RETURN = "PURCHASE_RETURN"
"""What a return calls itself on the stock movement it writes.

The movement register shows every change to a count and says which
document caused it, and these are the two new causes.
"""

ZERO = Decimal("0")

_WALK_IN = "Walk-in customer"
_NO_SUPPLIER = "No supplier"


def _lines_of(
    document,
    returned: dict[int, Decimal],
    names: dict[int, str],
    units: dict[int, str],
) -> tuple[ReturnableLine, ...]:
    """A document's lines with how much of each has already come back.

    Sale lines and purchase lines carry the same five facts under the same
    names, so one function serves both.
    """
    return tuple(
        ReturnableLine(
            line_id=line.id,
            item_type=line.item_type,
            inventory_item_id=line.inventory_item_id,
            label=names.get(line.inventory_item_id, "Unknown item"),
            quantity=line.quantity,
            returned=returned.get(line.id, ZERO),
            unit_price=line.unit_price,
            unit_label=units.get(line.uom_id) if line.uom_id else None,
        )
        for line in document.items
        if line.id is not None
    )


def _wanted(lines: list[ReturnedLineCommand]) -> dict[int, Decimal]:
    """How much is coming back off each line, one entry per line.

    A line named twice is one line coming back twice over, so the
    quantities are added: checking each half against the cap separately
    would let two halves through that the whole would not.
    """
    wanted: dict[int, Decimal] = {}
    for line in lines:
        quantity = to_quantity(line.quantity)
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        wanted[line.line_id] = wanted.get(line.line_id, ZERO) + quantity
    return wanted


def _returned_lines(
    document, wanted: dict[int, Decimal], returns, document_noun: str, traded: str
):
    """Each line being returned, paired with how many of it may be.

    Every line is checked before any of them moves stock: a return that
    fails on its second line must not leave the first one's goods back on
    the shelf. The unit of work would roll that back anyway — this is so
    the shopkeeper is told before anything is attempted at all.
    """
    checked = []
    for line_id, quantity in wanted.items():
        line = _line_of(document, line_id)
        if line is None:
            raise ValueError(f"That line is not on this {document_noun}.")

        # The whole point of anchoring a return to a line: a document can
        # give back what it sold and not one unit more.
        already = returns.returned_quantity_for_line(line.id)
        remaining = line.quantity - already
        if quantity > remaining:
            raise ValueError(
                f"Only {remaining} of one of these lines can still be returned — "
                f"{line.quantity} were {traded} and {already} have already come back."
            )
        checked.append((line, quantity))
    return checked


def _unit_labels(uow, document) -> dict[int, str]:
    """The names of the units this document's lines were entered in.

    Fetched for the ids on the document rather than by loading a SKU's
    units: a line says which unit it used, and the dialog only has to be
    able to write the word next to the number. Retired units are named
    too — a line entered in one still has to read back.
    """
    unit_ids = {line.uom_id for line in document.items if line.uom_id}
    if not unit_ids:
        return {}
    sku_units = UseCase.require(uow.sku_units, "sku_units")
    return sku_units.names_by_id(unit_ids)


def _line_of(document, line_id: int):
    """The line `line_id` names, if it is on this document at all.

    Checked rather than trusted: a line id that belongs to another invoice
    would otherwise return that invoice's goods against this one.
    """
    for line in document.items:
        if line.id == line_id:
            return line
    return None


class GetReturnableSaleUseCase(AuthenticatedUseCase[ReturnableDocumentQuery, ReturnableDocument]):
    """One sale, as the return dialog needs to see it.

    Reached either by id — the row action on the sales list, where the
    invoice is already in hand — or by invoice number, which is how the
    stock register asks. One use case for both, so the two entry points
    cannot come to different answers.
    """

    def __init__(self, uow: UnitOfWork, current_user_session=None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: ReturnableDocumentQuery) -> ReturnableDocument:
        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            returns = self.require(uow.sale_returns, "sale_returns")
            customers = self.require(uow.customers, "customers")
            items = self.require(uow.inventory_items, "inventory_items")

            sale = (
                sales.get_by_id(request.document_id)
                if request.document_id is not None
                else sales.get_by_invoice_no(request.reference.strip())
            )
            if sale is None:
                raise NotFoundError(f"No sale found for {request.wanted}")

            customer = (
                customers.get_by_id(sale.customer_id)
                if sale.customer_id is not None
                else None
            )
            names = items.names_by_id(
                {line.inventory_item_id for line in sale.items if line.inventory_item_id}
            )
            units = _unit_labels(uow, sale)
            return ReturnableDocument(
                document_id=sale.id,
                reference=sale.invoice_no,
                party_id=sale.customer_id,
                party_name=customer.name if customer else _WALK_IN,
                lines=_lines_of(sale, returns.returned_quantities_for_sale(sale.id), names, units),
                paid_amount=sale.paid_amount,
                balance_amount=sale.balance_amount,
                # What can honestly be handed back: money that came in and
                # has not already gone out again.
                refundable=sale.paid_amount - sale.refunded_amount,
            )


class GetReturnablePurchaseUseCase(
    AuthenticatedUseCase[ReturnableDocumentQuery, ReturnableDocument]
):
    """One purchase, as the return dialog needs to see it."""

    def __init__(self, uow: UnitOfWork, current_user_session=None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: ReturnableDocumentQuery) -> ReturnableDocument:
        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            returns = self.require(uow.purchase_returns, "purchase_returns")
            suppliers = self.require(uow.suppliers, "suppliers")
            items = self.require(uow.inventory_items, "inventory_items")

            purchase = (
                purchases.get_by_id(request.document_id)
                if request.document_id is not None
                else purchases.get_by_purchase_no(request.reference.strip())
            )
            if purchase is None:
                raise NotFoundError(f"No purchase found for {request.wanted}")

            supplier = (
                suppliers.get_by_id(purchase.supplier_id)
                if purchase.supplier_id is not None
                else None
            )
            names = items.names_by_id(
                {line.inventory_item_id for line in purchase.items if line.inventory_item_id}
            )
            units = _unit_labels(uow, purchase)
            return ReturnableDocument(
                document_id=purchase.id,
                reference=purchase.purchase_no,
                party_id=purchase.supplier_id,
                party_name=supplier.name if supplier else _NO_SUPPLIER,
                lines=_lines_of(
                    purchase,
                    returns.returned_quantities_for_purchase(purchase.id),
                    names,
                    units,
                ),
                paid_amount=purchase.paid_amount,
                balance_amount=purchase.balance_amount,
                refundable=purchase.paid_amount - purchase.refunded_amount,
            )


class RecordSaleReturnUseCase(AuthorizedUnitOfWorkUseCase[RecordSaleReturnCommand, SaleReturn]):
    """A customer brings goods back.

    Stock rises, the invoice is worth less, and — if money was handed over
    the counter — the till is lighter. All three, plus the return row
    itself, inside one transaction.
    """

    def execute(self, request: RecordSaleReturnCommand) -> SaleReturn:
        self.require_permission(Permission.MANAGE_SALES)

        if not request.lines:
            raise ValueError("A return needs at least one line.")
        if request.refund_amount < 0:
            raise ValueError("refund_amount cannot be negative")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            returns = self.require(uow.sale_returns, "sale_returns")
            movements = self.require(uow.inventory_movements, "inventory_movements")

            sale = sales.get_by_id(request.sale_id)
            if sale is None:
                raise NotFoundError(f"Sale id={request.sale_id} not found")

            returning = _returned_lines(
                sale, _wanted(request.lines), returns, "invoice", "sold"
            )

            return_no = request.return_no.strip()
            if returns.find_one_by("return_no", return_no) is not None:
                raise DuplicateEntityError(f"Return '{return_no}' already exists.")

            value = sum(
                (line.unit_price * Decimal(quantity) for line, quantity in returning),
                Decimal("0.00"),
            )
            if request.refund_amount > value:
                raise ValueError("A refund cannot exceed what the returned goods were worth.")

            # Money that never arrived cannot be handed back. Without this
            # a credit sale could be refunded in cash the shop never took.
            refundable = sale.paid_amount - sale.refunded_amount
            if request.refund_amount > refundable:
                raise ValueError(
                    f"Only {refundable} has been received on this invoice and is "
                    "available to refund."
                )

            saved = returns.add(
                SaleReturn(
                    return_no=return_no,
                    sale_id=sale.id,
                    items=[
                        SaleReturnItem(
                            sale_item_id=line.id,
                            item_type=line.item_type,
                            inventory_item_id=line.inventory_item_id,
                            quantity=quantity,
                            base_quantity=returned_base_quantity(line, quantity),
                            unit_price=line.unit_price,
                        )
                        for line, quantity in returning
                    ],
                    refund_amount=request.refund_amount,
                    refund_method_id=request.refund_method_id,
                    reason=request.reason,
                    note=request.note,
                    returned_at=now_pkt(),
                    created_by_user_id=current_user_id,
                )
            )

            for line, quantity in returning:
                target = load_stock_target(
                    uow=uow,
                    item_type=line.item_type,
                    inventory_item_id=line.inventory_item_id,
                )
                # Converted the way that line was, not the way its SKU
                # is configured today: a factor corrected since must not
                # change how much stock a return puts back.
                base_quantity = returned_base_quantity(line, quantity)
                previous_stock, resulting_stock = increase_stock(target.entity, base_quantity)
                target.repository.update(target.entity)

                # The stock register still shows the change, now with a
                # document behind it — which is what it never had before.
                # One row per line, because two items coming back are two
                # counts changing, and the register is read item by item.
                movements.add(
                    InventoryMovement(
                        movement_type=MovementType.RETURN,
                        item_type=line.item_type,
                        quantity=quantity,
                        uom_id=line.uom_id,
                        base_quantity=base_quantity,
                        inventory_item_id=line.inventory_item_id,
                        previous_stock=previous_stock,
                        resulting_stock=resulting_stock,
                        source_document_type=SALE_RETURN,
                        source_document_id=saved.id,
                        reference_no=f"{saved.return_no} · {sale.invoice_no}",
                        unit_price=line.unit_price,
                        reason=request.reason,
                        note=request.note,
                        created_by_user_id=current_user_id,
                    )
                )

            sale.returned_amount += value
            sale.refunded_amount += request.refund_amount
            sales.update(sale)

            return saved


class RecordPurchaseReturnUseCase(
    AuthorizedUnitOfWorkUseCase[RecordPurchaseReturnCommand, PurchaseReturn]
):
    """Goods go back to the supplier — the mirror, with stock falling."""

    def execute(self, request: RecordPurchaseReturnCommand) -> PurchaseReturn:
        self.require_permission(Permission.MANAGE_PURCHASES)

        if not request.lines:
            raise ValueError("A return needs at least one line.")
        if request.refund_amount < 0:
            raise ValueError("refund_amount cannot be negative")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            returns = self.require(uow.purchase_returns, "purchase_returns")
            movements = self.require(uow.inventory_movements, "inventory_movements")

            purchase = purchases.get_by_id(request.purchase_id)
            if purchase is None:
                raise NotFoundError(f"Purchase id={request.purchase_id} not found")

            returning = _returned_lines(
                purchase, _wanted(request.lines), returns, "purchase", "bought"
            )

            return_no = request.return_no.strip()
            if returns.find_one_by("return_no", return_no) is not None:
                raise DuplicateEntityError(f"Return '{return_no}' already exists.")

            value = sum(
                (line.unit_price * Decimal(quantity) for line, quantity in returning),
                Decimal("0.00"),
            )
            if request.refund_amount > value:
                raise ValueError("A refund cannot exceed what the returned goods were worth.")

            refundable = purchase.paid_amount - purchase.refunded_amount
            if request.refund_amount > refundable:
                raise ValueError(
                    f"Only {refundable} has been paid on this purchase and can be "
                    "refunded back."
                )

            saved = returns.add(
                PurchaseReturn(
                    return_no=return_no,
                    purchase_id=purchase.id,
                    items=[
                        PurchaseReturnItem(
                            purchase_item_id=line.id,
                            item_type=line.item_type,
                            inventory_item_id=line.inventory_item_id,
                            quantity=quantity,
                            base_quantity=returned_base_quantity(line, quantity),
                            unit_price=line.unit_price,
                        )
                        for line, quantity in returning
                    ],
                    refund_amount=request.refund_amount,
                    refund_method_id=request.refund_method_id,
                    reason=request.reason,
                    note=request.note,
                    returned_at=now_pkt(),
                    created_by_user_id=current_user_id,
                )
            )

            for line, quantity in returning:
                target = load_stock_target(
                    uow=uow,
                    item_type=line.item_type,
                    inventory_item_id=line.inventory_item_id,
                )
                # Converted at the bill's own conversion — see the sale
                # return above.
                base_quantity = returned_base_quantity(line, quantity)
                # Raises if the shelf no longer holds them — stock already
                # sold on cannot also be sent back to the supplier.
                previous_stock, resulting_stock = decrease_stock(target.entity, base_quantity)
                target.repository.update(target.entity)

                movements.add(
                    InventoryMovement(
                        movement_type=MovementType.RETURN,
                        item_type=line.item_type,
                        # Always positive; which way the count moved is
                        # read off previous/resulting stock — see
                        # InventoryMovement.quantity_change.
                        quantity=quantity,
                        uom_id=line.uom_id,
                        base_quantity=base_quantity,
                        inventory_item_id=line.inventory_item_id,
                        previous_stock=previous_stock,
                        resulting_stock=resulting_stock,
                        source_document_type=PURCHASE_RETURN,
                        source_document_id=saved.id,
                        reference_no=f"{saved.return_no} · {purchase.purchase_no}",
                        unit_price=line.unit_price,
                        reason=request.reason,
                        note=request.note,
                        created_by_user_id=current_user_id,
                    )
                )

            purchase.returned_amount += value
            purchase.refunded_amount += request.refund_amount
            purchases.update(purchase)

            return saved


class ListSaleReturnsUseCase(AuthenticatedUseCase[int, list[SaleReturn]]):
    """Every return against one sale, for its record card."""

    def __init__(self, uow: UnitOfWork, current_user_session=None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int) -> list[SaleReturn]:
        with self.uow as uow:
            return self.require(uow.sale_returns, "sale_returns").list_by_sale_id(request)


class ListPurchaseReturnsUseCase(AuthenticatedUseCase[int, list[PurchaseReturn]]):
    """Every return against one purchase, for its record card."""

    def __init__(self, uow: UnitOfWork, current_user_session=None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int) -> list[PurchaseReturn]:
        with self.uow as uow:
            return self.require(
                uow.purchase_returns, "purchase_returns"
            ).list_by_purchase_id(request)
