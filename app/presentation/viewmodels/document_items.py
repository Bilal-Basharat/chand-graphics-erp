"""
What a recorded document actually contained, ready to read underneath it:
the lines it was made of, and the instalments that settled it.

A sale line and a purchase line are the same record in opposite
directions — an item, a quantity and a unit price — and neither carries
the item's name, only its id. Both screens already load the catalogues
for their create dialog, so the lookup is fed from that and lives here
once instead of twice.

The same goes for payments. A sale, a purchase and a job are each paid in
instalments against a falling balance, and all six screens that show that
— the three document lists, the three payment lists — have to number and
total them identically or the same document reads two ways.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.presentation.formatting import DASH
from app.presentation.item_types import catalogue_key


@dataclass(frozen=True, slots=True)
class DocumentItemLine:
    """One line of a document, as it reads under the document itself."""

    label: str
    quantity: int
    unit_price: Decimal
    total: Decimal


class ItemCatalogue:
    """Names for the catalogue records that document lines point at.

    Filled from the ids on the page in hand rather than by loading a
    catalogue. Loading one meant a ceiling, and every line pointing at an
    item past that ceiling read as a dash — no error, no loading state,
    just a document that would not say what was on it.

    Names are added to rather than replaced: the ones fetched for the page
    before this cost nothing to keep and save asking for them again on the
    way back.
    """

    def __init__(self) -> None:
        self._names: dict[tuple[ItemType, int], str] = {}

    def add_names(self, item_type: ItemType, names: dict[int, str]) -> None:
        self._names.update(
            {(ItemType(item_type), item_id): name for item_id, name in names.items()}
        )

    def missing_ids(self, documents, item_type: ItemType) -> set[int]:
        """Which of these documents' lines this has no name for yet."""
        wanted = set()
        for document in documents:
            for line in document.items:
                kind, item_id = catalogue_key(line)
                if item_id and kind == item_type and (kind, item_id) not in self._names:
                    wanted.add(item_id)
        return wanted

    def label_for(self, item) -> str:
        return self._names.get(catalogue_key(item), DASH)

    def lines_of(self, document) -> list[DocumentItemLine]:
        return [
            DocumentItemLine(
                label=self.label_for(item),
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total_amount,
            )
            for item in document.items
        ]


@dataclass(frozen=True, slots=True)
class PaymentLine:
    """One instalment, as it reads underneath the document it settles."""

    when: datetime | None
    sequence: str
    """e.g. "Payment 2 of 3" — an instalment only means something in the
    context of the run it belongs to."""
    method: str
    amount: Decimal
    balance_after: Decimal
    """What was still owed once this one landed, so the column of balances
    walks down to zero exactly as the document was settled."""


def payment_lines(
    document,
    *,
    dated: Callable[[object], datetime | None],
    method_name: Callable[[int | None], str],
) -> list[PaymentLine]:
    """The instalments behind one document, oldest first.

    `dated` because each document stamps its payments under its own name
    — received_at on a sale, paid_at on a purchase — and `method_name`
    because the payment carries a method id, not a method.
    """
    payments = sorted(document.payments, key=lambda p: dated(p) or datetime.min)
    balance = document.grand_total
    lines: list[PaymentLine] = []
    for position, payment in enumerate(payments, start=1):
        # A refund is a negative payment, so this walks the balance back
        # up exactly as far as the money went back out.
        balance -= payment.amount
        method = method_name(payment.payment_method_id)
        lines.append(
            PaymentLine(
                when=dated(payment),
                sequence=f"Payment {position} of {len(payments)}",
                method=f"{method} • {payment.reference_no}" if payment.reference_no else method,
                amount=payment.amount,
                balance_after=balance,
            )
        )
    return lines


@dataclass(frozen=True, slots=True)
class ReturnLine:
    """One item that came back, on one return."""

    when: datetime | None
    reference: str
    """The return's own number, so the row on the card and the row in the
    stock register can be recognised as the same event."""
    label: str
    quantity: int
    value: Decimal
    refunded: Decimal
    """What was handed back for the whole return, against its first item
    only — see `return_lines`."""


def return_lines(returns, *, catalogue: ItemCatalogue) -> list[ReturnLine]:
    """What came back off one document, oldest first, one row per item.

    One function for sales and purchases: a return carries the same facts
    either way, and which direction the goods travelled is the card's
    caption, not the row's.

    A return can bring back several items at once, and each is its own
    row — that is what the card is being read for. The refund is not:
    one lot of goods going back is one movement of money, so it is shown
    once, against the first of them. Repeating it down the rows would
    read as a refund per item and total to several times what was paid.

    Names come from the catalogue the document's own lines already
    filled — a return is always of something that document sold or
    bought, so nothing extra has to be fetched.
    """
    return [
        ReturnLine(
            when=record.returned_at or record.created_at,
            reference=record.return_no,
            label=catalogue.label_for(item),
            quantity=item.quantity,
            value=item.total_amount,
            # Blank rather than zero on the rows after the first — see
            # `money_or_blank`, which the card renders it through.
            refunded=record.refund_amount if position == 0 else Decimal("0.00"),
        )
        for record in sorted(returns, key=lambda r: r.returned_at or datetime.min)
        for position, item in enumerate(record.items)
    ]


def returns_of(document, load, catalogue: ItemCatalogue) -> list[ReturnLine]:
    """What came back off `document`, fetched only if anything did.

    A document carries the value of its returns on itself, so the common
    case — nothing came back — is answered without a query at all. The one
    that did is a single lookup by document id, made when a card is
    opened rather than for every row of a list.
    """
    if not getattr(document, "returned_amount", 0):
        return []
    return return_lines(load(document.id), catalogue=catalogue)
