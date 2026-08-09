"""
What a recorded document actually contained, ready to read underneath it:
the lines it was made of, and the instalments that settled it.

A sale line and a purchase line are the same record in opposite
directions — a card or inventory item, a quantity and a unit price — and
neither carries the product's name, only its id. Both screens already
load the two catalogues for their create dialog, so the lookup is fed
from that and lives here once instead of twice.

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
from app.presentation.formatting import DASH, card_label


@dataclass(frozen=True, slots=True)
class DocumentItemLine:
    """One line of a document, as it reads under the document itself."""

    label: str
    quantity: int
    unit_price: Decimal
    total: Decimal


class ItemCatalogue:
    """Names for the cards and inventory items that document lines point at."""

    def __init__(self) -> None:
        self._names: dict[tuple[ItemType, int], str] = {}

    def set_products(self, cards: list, inventory_items: list) -> None:
        self._names = {(ItemType.CARD, card.id): card_label(card) for card in cards}
        self._names.update(
            {(ItemType.INVENTORY_ITEM, item.id): item.name for item in inventory_items}
        )

    def label_for(self, item) -> str:
        # Keyed off which id the line carries rather than off its declared
        # type: the two are guaranteed to agree by the line's own
        # invariant, and reading the id needs no enum round trip.
        key = (
            (ItemType.CARD, item.card_id)
            if item.card_id is not None
            else (ItemType.INVENTORY_ITEM, item.inventory_item_id)
        )
        return self._names.get(key, DASH)

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
