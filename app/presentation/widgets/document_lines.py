"""
The line items and money arithmetic shared by sales and purchases.

A sale ticket and a purchase both come down to the same thing: a list of
(item, quantity, unit price) lines, a discount, and an amount paid now.
Only the rules on the picking differ — a sale cannot sell stock that
isn't there, a purchase has no such limit — so the lines, their table,
and the totals live here and the two screens keep just their own rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from app.domain.enums.item_type import ItemType
from app.presentation.formatting import money, quantity
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.input_validation import ZERO
from app.presentation.widgets.row_actions import RowAction, RowActionsDelegate
from app.presentation.widgets.table_model import Column


@dataclass(slots=True)
class DocumentLine:
    item_type: ItemType
    item_id: int
    label: str
    quantity: Decimal
    unit_price: Decimal

    uom_id: int | None = None
    """Which of the item's units this line is counted in, or None for its
    own. Two lines of one item in different units are two lines: they are
    not the same number of the same thing."""

    unit_label: str | None = None
    """That unit's name, for the table. Carried rather than looked up: the
    line already knows which unit it chose."""

    base_quantity: Decimal | None = None
    """What the quantity comes to in the item's own unit.

    Held on the line because the screen has to add up several lines of
    one item to check them against the shelf, and boxes and pieces cannot
    be added together as they stand.
    """

    def __post_init__(self) -> None:
        if self.base_quantity is None:
            self.base_quantity = self.quantity

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def factor(self) -> Decimal:
        """How many base units one of this line's units is worth."""
        return self.base_quantity / self.quantity if self.quantity else Decimal("1")

    def set_quantity(self, quantity: Decimal) -> None:
        """Change how many, keeping the conversion this line was added at."""
        factor = self.factor
        self.quantity = quantity
        self.base_quantity = quantity * factor

    def matches(self, item_type: ItemType, item_id: int, uom_id: int | None = None) -> bool:
        return (
            self.item_type is item_type
            and self.item_id == item_id
            and self.uom_id == uom_id
        )

    def is_item(self, item_type: ItemType, item_id: int) -> bool:
        """The same item, whichever unit it was counted in."""
        return self.item_type is item_type and self.item_id == item_id


@dataclass(frozen=True, slots=True)
class DocumentTotals:
    subtotal: Decimal
    discount: Decimal
    grand_total: Decimal
    paid: Decimal
    balance: Decimal


def compute_totals(lines: list[DocumentLine], discount: Decimal, paid: Decimal) -> DocumentTotals:
    """Totals for a document being built.

    Discount and paid are clamped so a half-typed figure can never show a
    negative total while the user is still editing.
    """
    subtotal = sum((line.total for line in lines), ZERO)
    discount = min(max(discount, ZERO), subtotal)
    grand_total = subtotal - discount
    paid = max(paid, ZERO)
    return DocumentTotals(
        subtotal=subtotal,
        discount=discount,
        grand_total=grand_total,
        paid=paid,
        balance=max(grand_total - paid, ZERO),
    )


_EDIT = "edit"
_REMOVE = "remove"


class LinesTable(DataTable):
    """The line list for a document being built. Same columns either side
    of a sale/purchase, so the two read identically.

    Each row carries its own Edit and Remove buttons, so the row being
    acted on is the row under the pointer.
    """

    editRequested = Signal(int)    # row index
    removeRequested = Signal(int)  # row index

    def __init__(self, parent: QWidget | None = None) -> None:
        row_actions = RowActionsDelegate(
            [RowAction(_EDIT, "Edit"), RowAction(_REMOVE, "Remove", tone="danger")]
        )
        super().__init__(
            [
                # Kept narrow: this table also lives in the sale ticket's
                # side panel, where wide numeric columns would elide the
                # item name — the one column you need to read.
                Column("ITEM", lambda line: line.label),
                Column(
                    "QTY",
                    lambda line: quantity(line.quantity, line.unit_label),
                    align="right",
                    width=90,
                ),
                Column("UNIT PRICE", lambda line: money(line.unit_price), align="right", width=105),
                Column("LINE TOTAL", lambda line: money(line.total), align="right", width=115),
                # Unlabelled: a heading over two buttons names nothing the
                # buttons don't already say. Its width is whatever they
                # measure, so the labels can change without a magic number
                # here going stale.
                Column("", lambda _line: "", width=row_actions.column_width()),
            ],
            placeholder="No items yet.",
            parent=parent,
        )

        self._row_actions = row_actions
        row_actions.setParent(self)
        row_actions.attach(self, column=self._model.columnCount() - 1)
        row_actions.triggered.connect(self._on_action)

    def _on_action(self, key: str, row: int) -> None:
        signal = self.editRequested if key == _EDIT else self.removeRequested
        signal.emit(row)
