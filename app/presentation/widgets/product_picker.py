"""
The sellable catalogue as one searchable list, split into wedding cards
and everything else.

Both catalogues are sellable, so the picker shows them together rather
than making the user know in advance which module a product lives in.
They are still two different kinds of thing, though — a card has a number
and a design, an inventory item is stock by the ream — so they sit under
their own headings instead of being interleaved by name.

A list rather than a tile grid: at a few hundred products the grid became
a wall to scan, while a list gives every product the same line, the same
place for its stock figure, and a heading that says which kind it is.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QModelIndex, Signal
from PySide6.QtWidgets import QLineEdit, QSizePolicy, QVBoxLayout, QWidget

from app.domain.enums.item_type import ItemType
from app.presentation.formatting import card_label
from app.presentation.theme import tokens as t
from app.presentation.widgets.grouped_table import GroupedTable
from app.presentation.widgets.table_model import Column

_STOCK_WIDTH = 150


@dataclass(frozen=True, slots=True)
class Product:
    """What the picker needs from a card or an inventory item."""

    item_type: ItemType
    id: int
    label: str
    current_stock: int
    minimum_stock: int

    @property
    def sellable(self) -> bool:
        # Mirrors CreateSaleUseCase, which refuses to sell anything at or
        # below its minimum stock. Listing a product the sale would then
        # reject is worse than saying so up front.
        return self.current_stock > self.minimum_stock

    @property
    def blocked_reason(self) -> str:
        if self.current_stock <= 0:
            return "Out of stock"
        return f"At minimum ({self.current_stock} left)"

    @property
    def stock_text(self) -> str:
        return f"{self.current_stock} in stock" if self.sellable else self.blocked_reason

    def matches(self, term: str) -> bool:
        return term in self.label.lower()


@dataclass(frozen=True, slots=True)
class ProductGroup:
    title: str
    products: list[Product]


def product_from_card(card) -> Product:
    return Product(
        item_type=ItemType.CARD,
        id=card.id,
        label=card_label(card),
        current_stock=card.current_stock,
        minimum_stock=card.minimum_stock,
    )


def product_from_inventory_item(item) -> Product:
    return Product(
        item_type=ItemType.INVENTORY_ITEM,
        id=item.id,
        label=item.name,
        current_stock=item.current_stock,
        minimum_stock=item.minimum_stock,
    )


def _stock_color(product: Product) -> str:
    return t.INK_SOFT if product.sellable else t.DANGER


class ProductPicker(QWidget):
    """Search box over the grouped catalogue. Clicking a product picks it."""

    picked = Signal(object)  # Product

    def __init__(self, cards: list, inventory_items: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # A catalogue squeezed to two visible rows is a scrollbar, not a
        # list. It claims a real share of the dialog and grows with it.
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._groups = [
            ProductGroup("Wedding cards", [product_from_card(card) for card in cards]),
            ProductGroup(
                "Other items", [product_from_inventory_item(item) for item in inventory_items]
            ),
        ]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by card number or name")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _text: self._render())
        layout.addWidget(self._search)

        self._table = GroupedTable(
            [
                Column("PRODUCT", lambda group: group.title),
                Column(
                    "STOCK",
                    lambda group: _count_label(len(group.products)),
                    align="right",
                    width=_STOCK_WIDTH,
                ),
            ],
            [
                Column("", lambda product: product.label),
                Column(
                    "",
                    lambda product: product.stock_text,
                    align="right",
                    color=_stock_color,
                    width=_STOCK_WIDTH,
                ),
            ],
            children_of=lambda group: group.products,
            placeholder="No products to sell yet.",
            start_expanded=True,
        )
        self._table.setMinimumHeight(200)
        self._table.clicked.connect(self._on_clicked)
        layout.addWidget(self._table, 1)

        self._render()

    def _render(self) -> None:
        term = self._search.text().strip().lower()
        visible = [
            ProductGroup(
                group.title,
                [p for p in group.products if not term or p.matches(term)],
            )
            for group in self._groups
        ]
        # A heading over nothing is noise while filtering; with no filter it
        # is the honest answer that this catalogue is empty.
        if term:
            visible = [group for group in visible if group.products]
        self._table.set_placeholder(
            "Nothing matches this filter." if term else "No products to sell yet."
        )
        self._table.set_rows(visible)

    def _on_clicked(self, index: QModelIndex) -> None:
        product = self._table.detail_at(index)
        if product is not None:
            self.picked.emit(product)
            return
        # A heading is the one thing in the list that isn't a product, so
        # clicking it does the only thing it can mean: open or close it.
        # Normalised to column 0 — expansion belongs to the row, and Qt
        # tracks it against the index it was given.
        heading = index.sibling(index.row(), 0)
        self._table.setExpanded(heading, not self._table.isExpanded(heading))


def _count_label(count: int) -> str:
    return "1 product" if count == 1 else f"{count} products"
