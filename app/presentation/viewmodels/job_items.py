"""
What a job order was made of, ready to read underneath it.

The sibling of `document_items.py`, for the one document whose lines are
not a product and a price: a job item is a thing the shop made, out of
materials it took off its own shelves, with labour charged against it.

Kept apart from the view model that lists jobs because the job payments
screen shows the same jobs and has to describe them identically — the
lookups are the same lookups, so they are written once.
"""
from __future__ import annotations

from decimal import Decimal

from app.domain.enums.item_type import ItemType
from app.presentation.formatting import DASH, card_label, quantity


class JobItemLine:
    """One job item, as it reads in the disclosure under its job.

    Cost and charge, never the difference between them. The discount is
    struck against the job rather than the item, so a margin worked out
    per line would quietly disagree with the job's own figures.
    """

    __slots__ = ("label", "quantity", "unit_price", "total", "cost", "materials")

    def __init__(
        self,
        *,
        label: str,
        quantity: int,
        unit_price: Decimal,
        total: Decimal,
        cost: Decimal,
        materials: str,
    ) -> None:
        self.label = label
        self.quantity = quantity
        self.unit_price = unit_price
        self.total = total
        self.cost = cost
        self.materials = materials


class JobCatalogue:
    """Names for the products, materials and labour a job points at."""

    def __init__(self) -> None:
        self._products: dict[int, str] = {}
        self._labour: dict[int, str] = {}
        self._materials: dict[tuple[ItemType, int], str] = {}
        self._units: dict[tuple[ItemType, int], str | None] = {}

    def set_reference(
        self,
        *,
        product_types: list,
        labour_charge_types: list,
        cards: list,
        inventory_items: list,
    ) -> None:
        self._products = {p.id: p.name for p in product_types}
        self._labour = {c.id: c.name for c in labour_charge_types}
        self._materials = {
            (ItemType.CARD, card.id): card_label(card) for card in cards
        } | {(ItemType.INVENTORY_ITEM, item.id): item.name for item in inventory_items}
        # Cards are counted in cards, so they name no unit of their own.
        self._units = {(ItemType.CARD, card.id): None for card in cards} | {
            (ItemType.INVENTORY_ITEM, item.id): item.unit for item in inventory_items
        }

    def product_name(self, product_type_id: int) -> str:
        return self._products.get(product_type_id, DASH)

    def labour_name(self, labour_charge_type_id: int) -> str:
        return self._labour.get(labour_charge_type_id, DASH)

    def material_label(self, material) -> str:
        key = (
            (ItemType.CARD, material.card_id)
            if material.card_id is not None
            else (ItemType.INVENTORY_ITEM, material.inventory_item_id)
        )
        name = self._materials.get(key, DASH)
        return f"{name} — {quantity(material.quantity, self._units.get(key))}"

    def lines_of(self, job) -> list[JobItemLine]:
        return [
            JobItemLine(
                label=self.product_name(item.product_type_id),
                quantity=item.quantity,
                unit_price=item.unit_price,
                total=item.total_amount,
                cost=item.cost,
                materials=", ".join(self.material_label(m) for m in item.materials) or DASH,
            )
            for item in job.items
        ]
