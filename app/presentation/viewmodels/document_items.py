"""
What a recorded sale or purchase actually contained, ready to read
underneath it.

A sale line and a purchase line are the same record in opposite
directions — a card or inventory item, a quantity and a unit price — and
neither carries the product's name, only its id. Both screens already
load the two catalogues for their create dialog, so the lookup is fed
from that and lives here once instead of twice.
"""
from __future__ import annotations

from dataclasses import dataclass
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
