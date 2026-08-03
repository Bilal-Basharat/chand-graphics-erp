"""
The line items and money arithmetic shared by sales and purchases.

A sale ticket and a purchase both come down to the same thing: a list of
(item, quantity, unit price) lines, a discount, and an amount paid now.
Only the picking differs — a sale picks from card tiles, a purchase from
dropdowns — so the lines, their table, and the totals live here and the
two screens keep just their own way of choosing an item.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from app.domain.enums.item_type import ItemType
from app.presentation.formatting import money
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.row_actions import RowAction, RowActionsDelegate
from app.presentation.widgets.table_model import Column

ZERO = Decimal("0.00")


@dataclass(slots=True)
class DocumentLine:
    item_type: ItemType
    item_id: int
    label: str
    quantity: int
    unit_price: Decimal

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity

    def matches(self, item_type: ItemType, item_id: int) -> bool:
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


def parse_amount(text: str) -> Decimal | None:
    """A money figure typed by a user, or None if it isn't one."""
    try:
        return Decimal(text.strip())
    except (InvalidOperation, ValueError):
        return None


def parse_amount_or_zero(text: str) -> Decimal:
    value = parse_amount(text)
    return value if value is not None and value >= ZERO else ZERO


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
                Column("QTY", lambda line: line.quantity, align="right", width=60),
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
