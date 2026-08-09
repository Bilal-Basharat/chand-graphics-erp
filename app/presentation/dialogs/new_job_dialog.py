"""
New job order: who it is for, what is being made, and what was paid.

Laid out in the same three numbered steps as a sale and a purchase, and
sharing their totals panel, so the three transactions are recorded the
same way round. What a job adds is the fourth figure at the foot — what
the work cost the shop, and therefore whether it made money.

Step 2 is the purchase dialog's picker, item for item: the row describes
what is being made, the button adds it, and the table below is what has
been added so far. The one thing a job has that a purchase does not — the
stock and labour behind each item — opens as its own modal from that
button, because a window carrying the product row, a materials list and a
labour list at once is a form nobody can find their place in.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.application.dto.commands import (
    CreateJobCommand,
    JobItemCommand,
    JobLabourChargeCommand,
    JobMaterialCommand,
    JobPaymentCommand,
)
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.document_dialog import step_panel
from app.presentation.widgets.form_field import field
from app.presentation.dialogs.job_materials_dialog import (
    JobMaterialsDialog,
    LabourLine,
    Lines,
    MaterialLine,
    StockOption,
    stock_options,
)
from app.presentation.formatting import money
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.document_lines import ZERO, parse_amount
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.row_actions import RowAction, RowActionsDelegate
from app.presentation.widgets.table_model import Column
from app.presentation.widgets.totals_panel import TotalsPanel
from app.shared.datetimes import now_pkt

_WALK_IN = "Walk-in customer"
_NO_PRODUCTS = "— no product types —"
_MAX_QUANTITY = 10_000_000
_EDIT = "edit"
_REMOVE = "remove"
_ADD = "Add job item"
_SAVE = "Save job item"


def _new_job_number() -> str:
    return f"JOB-{now_pkt():%y%m%d%H%M%S}"


@dataclass(slots=True)
class _Entry:
    """One job item as entered: what is being made, and what goes into it.

    The command is assembled on demand rather than stored beside these
    fields, so there is only ever one copy of the material lines to keep
    in step when the item is edited.
    """

    product_type_id: int
    label: str
    quantity: int
    unit_price: Decimal
    specifications: str | None
    materials: list[MaterialLine]
    labour: list[LabourLine]

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def cost(self) -> Decimal:
        return sum((m.total for m in self.materials), ZERO) + sum(
            (c.amount for c in self.labour), ZERO
        )

    def command(self) -> JobItemCommand:
        return JobItemCommand(
            product_type_id=self.product_type_id,
            quantity=self.quantity,
            unit_price=self.unit_price,
            specifications=self.specifications,
            materials=[
                JobMaterialCommand(
                    item_type=line.item_type,
                    quantity=line.quantity,
                    card_id=line.item_id if line.item_type is ItemType.CARD else None,
                    inventory_item_id=None if line.item_type is ItemType.CARD else line.item_id,
                    unit_cost=line.unit_cost,
                )
                for line in self.materials
            ],
            labour_charges=[
                JobLabourChargeCommand(
                    labour_charge_type_id=line.labour_charge_type_id, amount=line.amount
                )
                for line in self.labour
            ],
        )


class NewJobDialog(QDialog):
    def __init__(
        self,
        view_model,
        *,
        customers: list,
        payment_methods: list,
        product_types: list,
        labour_charge_types: list,
        cards: list,
        inventory_items: list,
        current_user_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New job order")
        self.setModal(True)

        self._view_model = view_model
        self._customers = customers
        self._product_types = product_types
        self._labour_charge_types = labour_charge_types
        self._stock: list[StockOption] = stock_options(cards, inventory_items)
        self._current_user_id = current_user_id
        self._entries: list[_Entry] = []
        # Which row the picker is currently standing in for, if any. None
        # means it is describing a new item.
        self._editing: int | None = None

        frame = QVBoxLayout(self)
        frame.setContentsMargins(0, 0, 0, 0)
        frame.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("PageScrollBody")
        scroll.setWidget(body)
        frame.addWidget(scroll, 1)

        outer = QVBoxLayout(body)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        heading = QLabel("New job order")
        heading.setProperty("role", "pageTitle")
        caption = QLabel("Record what was ordered, what it takes to make, and what was paid.")
        caption.setProperty("role", "pageSub")
        outer.addWidget(heading)
        outer.addWidget(caption)

        outer.addWidget(self._build_identity_step())
        outer.addWidget(self._build_items_step(), 1)
        outer.addWidget(self._build_payment_step(payment_methods))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._submit_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self._submit_button.setText("Record job")
        self._submit_button.setProperty("variant", "primary")
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(24, 12, 24, 16)
        footer_layout.addWidget(buttons)
        frame.addWidget(footer)

        self._size_to_screen(body, footer)

        self._connections = [
            (view_model.itemCreated, self._on_created),
            (view_model.errorOccurred, self._on_error),
        ]
        for signal, slot in self._connections:
            signal.connect(slot)

        self._render()

    def _size_to_screen(self, body: QWidget, footer: QWidget) -> None:
        available = self.screen().availableGeometry()
        margin = 80
        wanted = body.sizeHint().height() + footer.sizeHint().height()
        self.setMinimumWidth(min(920, available.width() - margin))
        self.resize(
            min(1040, available.width() - margin),
            min(wanted, available.height() - margin),
        )

    # ---------------- step 1 ----------------

    def _build_identity_step(self) -> QFrame:
        panel, layout = step_panel("1", "Job and customer")

        row = QHBoxLayout()
        row.setSpacing(12)

        self._job_no = QLineEdit(_new_job_number())
        self._customer = QComboBox()
        self._customer.addItem(_WALK_IN, None)
        for customer in self._customers:
            self._customer.addItem(customer.name, customer.id)

        self._promised = QDateEdit()
        self._promised.setCalendarPopup(True)
        self._promised.setDisplayFormat("dd MMM yyyy")
        self._promised.setSpecialValueText("Not promised")
        # The minimum doubles as "no date": a job with no promised day is
        # ordinary, and an empty date edit has no other way to say so.
        self._promised.setMinimumDate(QDate(2000, 1, 1))
        self._promised.setDate(self._promised.minimumDate())

        row.addLayout(field("Job number", self._job_no), 1)
        row.addLayout(field("Customer", self._customer), 1)
        row.addLayout(field("Promised for", self._promised), 1)
        layout.addLayout(row)
        return panel

    # ---------------- step 2 ----------------

    def _build_items_step(self) -> QFrame:
        panel, layout = step_panel("2", "What is being made")
        layout.addWidget(self._build_picker())

        actions = RowActionsDelegate(
            [RowAction(_EDIT, "Edit"), RowAction(_REMOVE, "Remove", tone="danger")]
        )
        self._items_table = DataTable(
            [
                Column("PRODUCT", lambda e: e.label, width=160),
                # The only free-text column, so it takes the leftover
                # space: a specification is a sentence, and elided to
                # "100 pages each, ha…" it says nothing.
                Column("SPECIFICATIONS", lambda e: e.specifications or "—"),
                Column("QTY", lambda e: e.quantity, align="right", width=70),
                Column("PRICE EACH", lambda e: money(e.unit_price), align="right", width=110),
                Column("CHARGED", lambda e: money(e.total), align="right", width=115),
                Column("COSTS", lambda e: money(e.cost), align="right", width=115),
                Column("", lambda _e: "", width=actions.column_width()),
            ],
            placeholder="Nothing added yet — describe the first item above.",
        )
        self._items_table.setMinimumHeight(160)
        actions.setParent(self._items_table)
        actions.attach(self._items_table, column=6)
        actions.triggered.connect(self._on_row_action)
        layout.addWidget(self._items_table, 1)
        return panel

    def _build_picker(self) -> QWidget:
        """The customer's half of an item, on one line.

        Product, specification, how many and the price each are what is
        agreed at the counter, and they are agreed together — so they are
        typed together, and the button beside them opens the shop's half.
        """
        picker = QWidget()
        row = QHBoxLayout(picker)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self._product = QComboBox()
        self._product.setMinimumWidth(180)
        if self._product_types:
            for product_type in self._product_types:
                self._product.addItem(product_type.name, product_type.id)
        else:
            self._product.addItem(_NO_PRODUCTS, None)

        self._specifications = QLineEdit()
        self._specifications.setPlaceholderText("e.g. 100 pages each, half A4 per page")

        self._quantity = ModernSpinBox()
        self._quantity.setRange(1, _MAX_QUANTITY)
        self._quantity.setValue(1)

        self._unit_price = QLineEdit()
        self._unit_price.setPlaceholderText("0.00")
        self._unit_price.setMaximumWidth(120)
        self._unit_price.returnPressed.connect(self._submit_picker)

        self._add_button = QPushButton(_ADD)
        self._add_button.setProperty("variant", "primary")
        self._add_button.clicked.connect(self._submit_picker)

        # Only while an existing row is loaded into these fields: without
        # it, the way out of editing would be to save a change you didn't
        # want to make.
        self._cancel_edit_button = QPushButton("Cancel edit")
        self._cancel_edit_button.setProperty("variant", "outline")
        self._cancel_edit_button.clicked.connect(self._exit_edit)
        self._cancel_edit_button.hide()

        row.addLayout(field("Product", self._product), 1)
        row.addLayout(field("Specifications", self._specifications), 2)
        row.addLayout(field("Quantity", self._quantity))
        row.addLayout(field("Price each", self._unit_price))
        row.addLayout(field("", self._add_button))
        row.addLayout(field("", self._cancel_edit_button))
        return picker

    def _on_row_action(self, key: str, row: int) -> None:
        if not 0 <= row < len(self._entries):
            return
        if key == _REMOVE:
            del self._entries[row]
            # Dropped rather than re-aimed: the row numbers behind it have
            # all shifted, and silently editing a different item than the
            # one that was loaded would be worse than starting again.
            self._exit_edit()
            self._render()
            return
        self._open_edit_menu(row)

    def _open_edit_menu(self, row: int) -> None:
        """Ask which half of the item is being corrected.

        "Edit" means two different things on a job item — what was agreed
        with the customer, or what the shop puts into it — and they live
        in two different places. Guessing one would send the user to the
        wrong form half the time.

        Popped at the pointer because the actions are painted by a
        delegate rather than being widgets, so there is no button to
        anchor a menu to; the pointer is on it either way.
        """
        menu = QMenu(self)
        menu.addAction("Edit job item", lambda: self._edit_details(row))
        menu.addAction("Edit materials and labour", lambda: self._edit_materials(row))
        menu.exec(QCursor.pos())

    def _edit_details(self, row: int) -> None:
        """Load an item back into the picker it was entered through.

        There is only one way to describe a job item on this screen, and
        it is the row above the table — so correcting one happens there
        too, rather than in a second form of the same four fields.
        """
        entry = self._entries[row]
        self._product.setCurrentIndex(max(self._product.findData(entry.product_type_id), 0))
        self._specifications.setText(entry.specifications or "")
        self._quantity.setValue(entry.quantity)
        self._unit_price.setText(f"{entry.unit_price:.2f}")
        self._editing = row
        self._sync_picker_mode()
        self._product.setFocus()

    def _edit_materials(self, row: int) -> None:
        entry = self._entries[row]
        lines = self._open_materials(
            product_label=entry.label,
            quantity=entry.quantity,
            materials=entry.materials,
            labour=entry.labour,
            editing=True,
        )
        if lines is None:
            return
        entry.materials, entry.labour = lines
        self._render()

    def _open_materials(
        self,
        *,
        product_label: str,
        quantity: int,
        materials: list[MaterialLine] | None,
        labour: list[LabourLine] | None,
        editing: bool,
    ) -> Lines | None:
        dialog = JobMaterialsDialog(
            self._view_model,
            product_label=product_label,
            quantity=quantity,
            labour_charge_types=self._labour_charge_types,
            stock=self._stock,
            materials=materials,
            labour=labour,
            editing=editing,
            parent=self,
        )
        dialog.exec()
        return dialog.lines()

    def _submit_picker(self) -> None:
        """What the button under the picker does — add a new item, or save
        the one loaded into it."""
        product_type_id = self._product.currentData()
        if product_type_id is None:
            self._warn(
                "There are no product types yet. Add one under Items → Product types, "
                "then record this job."
            )
            return

        price = parse_amount(self._unit_price.text())
        if price is None or price < ZERO:
            self._warn("Enter the price of one of these.")
            self._unit_price.setFocus()
            return

        quantity = self._quantity.value()
        specifications = self._specifications.text().strip() or None

        if self._editing is not None:
            entry = self._entries[self._editing]
            entry.product_type_id = product_type_id
            entry.label = self._product.currentText()
            entry.quantity = quantity
            entry.unit_price = price
            entry.specifications = specifications
            # Its materials and labour are untouched — they are edited
            # from the other half of the same menu.
            self._exit_edit()
            self._render()
            return

        lines = self._open_materials(
            product_label=self._product.currentText(),
            quantity=quantity,
            materials=None,
            labour=None,
            editing=False,
        )
        if lines is None:
            return

        materials, labour = lines
        self._entries.append(
            _Entry(
                product_type_id=product_type_id,
                label=self._product.currentText(),
                quantity=quantity,
                unit_price=price,
                specifications=specifications,
                materials=materials,
                labour=labour,
            )
        )
        self._reset_picker()
        self._render()

    def _exit_edit(self) -> None:
        self._editing = None
        self._sync_picker_mode()
        self._reset_picker()

    def _sync_picker_mode(self) -> None:
        editing = self._editing is not None
        self._add_button.setText(_SAVE if editing else _ADD)
        self._cancel_edit_button.setVisible(editing)

    def _reset_picker(self) -> None:
        """Clear the row down for the next product, and put the cursor back
        at the start of it."""
        self._specifications.clear()
        self._quantity.setValue(1)
        self._unit_price.clear()
        self._product.setFocus()

    # ---------------- step 3 ----------------

    def _build_payment_step(self, payment_methods: list) -> QFrame:
        """The same money block a sale and a purchase end on: subtotal,
        total, and what is left to pay.

        What the job cost the shop is not repeated here. It is on every
        item's own row above, and the margin between the two is a figure
        for the job list to report once the job exists — putting it in
        front of someone still agreeing a price invites the price to be
        set from it.
        """
        panel, layout = step_panel("3", "Discount and payment")
        self._totals = TotalsPanel(paid_caption="Paid now")
        self._totals.set_payment_methods(payment_methods)
        self._totals.changed.connect(self._render_totals)
        layout.addWidget(self._totals)
        return panel

    # ---------------- rendering ----------------

    def _render(self) -> None:
        self._items_table.set_rows(list(self._entries))
        self._submit_button.setEnabled(bool(self._entries))
        self._render_totals()

    def _render_totals(self) -> None:
        # TotalsPanel works in DocumentLines; a job item is close enough in
        # shape to feed it directly.
        self._totals.render(self._entries)

    # ---------------- submit ----------------

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, "New job order", message)

    def _submit(self) -> None:
        if not self._job_no.text().strip():
            self._warn("Job number is required.")
            self._job_no.setFocus()
            return
        if not self._entries:
            self._warn("Add at least one job item first.")
            return

        totals = self._totals.render(self._entries)
        if totals.paid > totals.grand_total:
            self._warn("Paid now is more than the total. Reduce it or add a discount.")
            self._totals.focus_paid()
            return
        if totals.paid > ZERO and self._current_user_id is None:
            self._warn("Your session has ended. Sign in again to record a payment.")
            return

        payments = []
        if totals.paid > ZERO:
            payments.append(
                JobPaymentCommand(
                    amount=totals.paid,
                    payment_method_id=self._totals.payment_method_id,
                    received_by_user_id=self._current_user_id,
                )
            )

        promised = self._promised.date()
        command = CreateJobCommand(
            job_no=self._job_no.text().strip(),
            customer_id=self._customer.currentData(),
            promised_date=(
                None if promised == self._promised.minimumDate() else promised.toPython()
            ),
            discount_amount=totals.discount,
            items=[entry.command() for entry in self._entries],
            payments=payments,
        )

        self._submit_button.setEnabled(False)
        self._view_model.create(command)

    def _on_created(self, *_result) -> None:
        self.accept()

    def _on_error(self, message: str) -> None:
        self._submit_button.setEnabled(bool(self._entries))
        self._warn(message)

    def done(self, result: int) -> None:  # noqa: D102 (Qt override)
        for signal, slot in self._connections:
            signal.disconnect(slot)
        self._connections.clear()
        super().done(result)
