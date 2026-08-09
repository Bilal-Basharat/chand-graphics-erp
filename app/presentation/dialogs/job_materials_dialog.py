"""
What goes into one thing the shop was asked to make.

The job dialog behind this one has already settled the customer's half of
the item — which product, how many, and the price each. This is the
shop's own half: the stock it eats and the work it takes. Kept in its own
modal because the two halves are two different questions, and a single
window carrying a product picker, a materials list and a labour list at
once is a form nobody can find their place in.

Materials and labour are added a line at a time within this dialog rather
than through a sub-dialog each: a bill book eats three or four materials,
and a modal per line for that many turns one job into a dozen dismissals.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.formatting import card_label, money, quantity as quantity_label
from app.presentation.theme import tokens as t
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.document_lines import ZERO, parse_amount
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.row_actions import RowAction, RowActionsDelegate
from app.presentation.widgets.table_model import Column

_MAX_QUANTITY = 10_000_000
_REMOVE = "remove"

Lines = tuple[list["MaterialLine"], list["LabourLine"]]


@dataclass(slots=True)
class MaterialLine:
    item_type: ItemType
    item_id: int
    label: str
    unit: str | None
    quantity: int
    unit_cost: Decimal
    available: int

    @property
    def total(self) -> Decimal:
        return self.unit_cost * self.quantity

    @property
    def quantity_text(self) -> str:
        return quantity_label(self.quantity, self.unit)


@dataclass(slots=True)
class LabourLine:
    labour_charge_type_id: int
    label: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class StockOption:
    """A stock item the job can consume, as the picker needs it."""

    item_type: ItemType
    id: int
    label: str
    unit: str | None
    current_stock: int

    @property
    def stock_text(self) -> str:
        return f"{quantity_label(self.current_stock, self.unit)} in stock"


def stock_options(cards: list, inventory_items: list) -> list[StockOption]:
    """Everything the shop holds, materials first.

    Inventory items lead because paper, ink and gum are what a job
    normally eats; cards are consumed only by card-printing work.
    """
    return [
        StockOption(
            item_type=ItemType.INVENTORY_ITEM,
            id=item.id,
            label=item.name,
            unit=item.unit,
            current_stock=item.current_stock,
        )
        for item in inventory_items
    ] + [
        StockOption(
            item_type=ItemType.CARD,
            id=card.id,
            label=card_label(card),
            unit=None,
            current_stock=card.current_stock,
        )
        for card in cards
    ]


class JobMaterialsDialog(FormDialog):
    """Collects the materials and labour for one job item.

    `lines()` returns them once the dialog has been accepted, or None if
    it was dismissed.
    """

    def __init__(
        self,
        view_model,
        *,
        product_label: str,
        quantity: int,
        labour_charge_types: list,
        stock: list[StockOption],
        materials: list[MaterialLine] | None = None,
        labour: list[LabourLine] | None = None,
        editing: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title="Materials and labour",
            subtitle=f"What goes into {quantity} × {product_label}, and what it costs.",
            submit_label="Save item" if editing else "Add item",
            parent=parent,
        )
        self.setMinimumWidth(720)

        self._view_model = view_model
        self._stock = {(option.item_type, option.id): option for option in stock}
        self._materials: list[MaterialLine] = list(materials or [])
        self._labour: list[LabourLine] = list(labour or [])
        self._result: Lines | None = None

        # What the last purchase of the selected material cost, and whether
        # that answer is still on its way. Held rather than read back out
        # of the field, because the field is not one the user can type in.
        self._unit_cost: Decimal | None = None
        self._cost_pending = False

        self._outer.insertWidget(self._outer.count() - 1, self._build_materials())
        self._outer.insertWidget(self._outer.count() - 1, self._build_labour())
        self._outer.insertWidget(self._outer.count() - 1, self._build_summary())

        for option in stock:
            self._material_picker.addItem(
                f"{option.label}  ·  {option.stock_text}", (option.item_type, option.id)
            )
        for charge_type in labour_charge_types:
            self._labour_picker.addItem(charge_type.name, charge_type.id)

        self._render_materials()
        self._render_labour()
        self._on_material_picked()
        self._recompute()

    # ---------------- materials ----------------

    def _build_materials(self) -> QFrame:
        panel, layout = _section("Materials used", "Deducted from stock when the job is recorded.")

        picker_row = QHBoxLayout()
        picker_row.setSpacing(10)

        self._material_picker = QComboBox()
        self._material_picker.currentIndexChanged.connect(lambda _i: self._on_material_picked())

        self._material_quantity = ModernSpinBox()
        self._material_quantity.setRange(1, _MAX_QUANTITY)
        self._material_quantity.setFixedWidth(120)

        # Read-only, and greyed by the stylesheet's :read-only rule. What a
        # material costs the shop is settled by the purchase that brought
        # it in; letting a job restate it here would put two different
        # answers in the books for the same tin of ink, and what the job
        # cost would be whichever one was typed last.
        self._material_cost = QLineEdit()
        self._material_cost.setReadOnly(True)
        self._material_cost.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._material_cost.setFixedWidth(120)

        add = QPushButton("Add material")
        add.setProperty("variant", "outline")
        add.clicked.connect(self._add_material)

        picker_row.addLayout(_field("Material", self._material_picker), 1)
        picker_row.addLayout(_field("Quantity", self._material_quantity))
        picker_row.addLayout(_field("Cost each", self._material_cost))
        picker_row.addLayout(_field("", add))
        layout.addLayout(picker_row)

        self._material_hint = QLabel("")
        self._material_hint.setProperty("role", "fieldHelp")
        layout.addWidget(self._material_hint)

        self._materials_table = _lines_table(
            [
                Column("MATERIAL", lambda line: line.label),
                Column("QTY", lambda line: line.quantity_text, align="right", width=110),
                Column("COST EACH", lambda line: money(line.unit_cost), align="right", width=105),
                Column("LINE COST", lambda line: money(line.total), align="right", width=110),
            ],
            "No materials added yet.",
            self._remove_material,
        )
        layout.addWidget(self._materials_table)
        return panel

    def _on_material_picked(self) -> None:
        """Show the last price paid for whatever is selected.

        Fetched rather than remembered: the catalogue holds no price, so
        the only honest figure is the most recent purchase — and it may
        have changed since this dialog opened.
        """
        key = self._material_picker.currentData()
        if key is None:
            return
        option = self._stock[tuple(key)]
        # Capped at what is actually there, so the stepper cannot walk past
        # the stock the job would then be refused for.
        self._material_quantity.setRange(1, max(option.current_stock, 1))
        self._material_hint.setText(f"{option.stock_text}.")
        self._material_cost.clear()
        self._unit_cost = None
        self._cost_pending = True

        def _apply(cost: Decimal | None) -> None:
            # Guard against a slow lookup landing after the user has moved
            # on to a different material.
            if self._material_picker.currentData() != key:
                return
            self._cost_pending = False
            self._unit_cost = cost
            if cost is None:
                self._material_hint.setText(
                    f"{option.stock_text}. Never purchased, so it has no cost yet — "
                    "record a purchase for it first."
                )
                return
            self._material_cost.setText(f"{cost:.2f}")

        self._view_model.material_unit_cost(option.item_type, option.id, _apply)

    def _add_material(self) -> None:
        key = self._material_picker.currentData()
        if key is None:
            self.reject_with("Add a material to the catalogue first.")
            return
        option = self._stock[tuple(key)]

        if self._cost_pending:
            self.reject_with(f"Still looking up what '{option.label}' costs — try again in a moment.")
            return
        if self._unit_cost is None:
            self.reject_with(
                f"'{option.label}' has never been purchased, so there is no cost to "
                "charge this job with. Record a purchase for it first."
            )
            return

        wanted = self._material_quantity.value()
        already = sum(
            line.quantity
            for line in self._materials
            if line.item_type is option.item_type and line.item_id == option.id
        )
        if already + wanted > option.current_stock:
            self.reject_with(
                f"Only {quantity_label(option.current_stock, option.unit)} of "
                f"'{option.label}' in stock"
                + (f", and {already} already on this item." if already else "."),
                self._material_quantity,
            )
            return

        self._materials.append(
            MaterialLine(
                item_type=option.item_type,
                item_id=option.id,
                label=option.label,
                unit=option.unit,
                quantity=wanted,
                unit_cost=self._unit_cost,
                available=option.current_stock,
            )
        )
        self._material_quantity.setValue(1)
        self._render_materials()
        self._recompute()
        self._material_picker.setFocus()

    def _remove_material(self, row: int) -> None:
        if 0 <= row < len(self._materials):
            del self._materials[row]
            self._render_materials()
            self._recompute()

    def _render_materials(self) -> None:
        self._materials_table.set_rows(list(self._materials))

    # ---------------- labour ----------------

    def _build_labour(self) -> QFrame:
        panel, layout = _section(
            "Labour charges",
            "Optional. What the work cost the shop — not billed to the customer separately.",
        )

        picker_row = QHBoxLayout()
        picker_row.setSpacing(10)

        self._labour_picker = QComboBox()

        self._labour_amount = QLineEdit()
        self._labour_amount.setPlaceholderText("0.00")
        self._labour_amount.setFixedWidth(140)
        self._labour_amount.returnPressed.connect(self._add_labour)

        add = QPushButton("Add labour charge")
        add.setProperty("variant", "outline")
        add.clicked.connect(self._add_labour)

        picker_row.addLayout(_field("Work", self._labour_picker), 1)
        picker_row.addLayout(_field("Amount", self._labour_amount))
        picker_row.addLayout(_field("", add))
        layout.addLayout(picker_row)

        self._labour_table = _lines_table(
            [
                Column("WORK", lambda line: line.label),
                Column("AMOUNT", lambda line: money(line.amount), align="right", width=140),
            ],
            "No labour charges on this item.",
            self._remove_labour,
        )
        layout.addWidget(self._labour_table)
        return panel

    def _add_labour(self) -> None:
        charge_type_id = self._labour_picker.currentData()
        if charge_type_id is None:
            self.reject_with("Add a labour charge to the catalogue first.")
            return

        amount = parse_amount(self._labour_amount.text())
        if amount is None or amount < ZERO:
            self.reject_with("Enter what this work cost.", self._labour_amount)
            return

        self._labour.append(
            LabourLine(
                labour_charge_type_id=charge_type_id,
                label=self._labour_picker.currentText(),
                amount=amount,
            )
        )
        self._labour_amount.clear()
        self._render_labour()
        self._recompute()
        self._labour_picker.setFocus()

    def _remove_labour(self, row: int) -> None:
        if 0 <= row < len(self._labour):
            del self._labour[row]
            self._render_labour()
            self._recompute()

    def _render_labour(self) -> None:
        self._labour_table.set_rows(list(self._labour))

    # ---------------- summary ----------------

    def _build_summary(self) -> QWidget:
        """What this item costs the shop, and nothing else.

        The price the customer pays was settled on the row this dialog was
        opened from, and the margin between the two is a fact about the
        whole job — the discount is struck there, not here. Showing either
        of them beside these lines would invite the two halves of the job
        to be read as one sum.
        """
        strip = QWidget()
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(26)
        layout.addStretch(1)

        self._cost_label = _figure(t.INK)
        block = QVBoxLayout()
        block.setSpacing(2)
        caption = QLabel("Cost — materials and labour")
        caption.setProperty("role", "statLabel")
        caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._cost_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        block.addWidget(caption)
        block.addWidget(self._cost_label)
        layout.addLayout(block)
        return strip

    def _recompute(self) -> None:
        cost = sum((line.total for line in self._materials), ZERO) + sum(
            (line.amount for line in self._labour), ZERO
        )
        self._cost_label.setText(money(cost))

    # ---------------- submit ----------------

    def build_command(self) -> Lines | None:
        # An item made of nothing costs nothing, and what a job cost is
        # the one figure this module exists to get right. Labour alone is
        # a real case — trimming or binding work the shop took no stock
        # for — so either side satisfies this.
        if not self._materials and not self._labour:
            self.reject_with(
                "Add what this item is made from — at least one material, or a "
                "labour charge if it used none."
            )
            return None
        return list(self._materials), list(self._labour)

    def submit_command(self, command: Lines) -> None:
        # Nothing to persist here — the job dialog collects the items and
        # records them all in one write.
        self._result = command
        self.accept()

    def lines(self) -> Lines | None:
        """The materials and labour as entered, or None if the dialog was
        dismissed."""
        return self._result


# ---------------- small shared pieces ----------------


def _field(label_text: str, field: QWidget) -> QVBoxLayout:
    block = QVBoxLayout()
    block.setSpacing(5)
    label = QLabel(label_text or " ")
    label.setProperty("role", "fieldLabel")
    block.addWidget(label)
    block.addWidget(field)
    return block


def _section(title: str, subtitle: str) -> tuple[QFrame, QVBoxLayout]:
    panel = QFrame()
    panel.setProperty("role", "panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(9)

    heading = QLabel(title)
    heading.setProperty("role", "panelTitle")
    caption = QLabel(subtitle)
    caption.setProperty("role", "panelSub")
    caption.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(caption)
    return panel, layout


def _lines_table(columns: list[Column], placeholder: str, on_remove) -> DataTable:
    actions = RowActionsDelegate([RowAction(_REMOVE, "Remove", tone="danger")])
    table = DataTable(
        [*columns, Column("", lambda _line: "", width=actions.column_width())],
        placeholder=placeholder,
    )
    table.setMinimumHeight(110)
    table.setMaximumHeight(190)
    actions.setParent(table)
    actions.attach(table, column=len(columns))
    actions.triggered.connect(lambda _key, row: on_remove(row))
    return table


def _figure(color: str) -> QLabel:
    label = QLabel(money(ZERO))
    label.setStyleSheet(f"color: {color}; font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 15px;")
    return label
