"""
Expenses screen: period-filtered list plus a create dialog.

The collection scaffold with one addition — a period selector, since
expenses are fetched by date range rather than listed whole.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QComboBox, QLineEdit, QTextEdit, QWidget

from app.application.dto.commands import CreateExpenseCommand
from app.container import AppContainer
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.formatting import DASH, date_time, money, or_dash
from app.presentation.records.builders import expense_card
from app.presentation.records.card import RecordCard
from app.presentation.theme import tokens as t
from app.presentation.viewmodels.collection_viewmodel import CollectionSource, CollectionViewModel
from app.presentation.views.collection_view import VIEW_ACTION, CollectionPage, CollectionView
from app.presentation.widgets.list_controls import FilterOption
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.quick_add_strip import QuickAddField, combo, line_edit, refill
from app.presentation.widgets.period_selector import PeriodSelection, PeriodSelector
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.table_model import Column

_NO_CATEGORY = "— Uncategorised —"


def _spent_at(expense) -> datetime:
    """Sort key that never trips over a missing timestamp."""
    return expense.created_at or datetime.min


def expenses_view_model(container: AppContainer, period: PeriodSelection) -> CollectionViewModel:
    return CollectionViewModel(
        CollectionSource(
            list_all=lambda: container.list_expenses_by_date_range_use_case().execute(period.as_query()),
            create=lambda command: container.create_expense_use_case().execute(command),
        )
    )


class ExpensesView(CollectionView):
    def __init__(
        self,
        view_model: CollectionViewModel,
        period: PeriodSelection,
        categories: CollectionViewModel,
        parent: QWidget | None = None,
    ) -> None:
        # Set before super().__init__ — the base builds the toolbar, which
        # reads these, before its own constructor returns.
        self._period = period
        self._categories = categories
        self._category_names: dict[int, str] = {}

        super().__init__(
            CollectionPage(
                crumb=("Finance", "Expenses"),
                title="Expenses",
                subtitle="Money spent running the press, grouped by category and filtered by period.",
                panel_title="Expense list",
                empty_message="No expenses in this period.",
                unit="expense",
                create_label="Record expense",
            ),
            [
                Column("EXPENSE", lambda e: e.expense_name),
                Column("CATEGORY", self._category_label, width=180),
                Column(
                    "QTY",
                    lambda e: or_dash(e.quantity),
                    align="right",
                    sort_key=lambda e: e.quantity or 0,
                    width=80,
                ),
                Column(
                    "UNIT PRICE",
                    lambda e: money(e.unit_price),
                    align="right",
                    sort_key=lambda e: e.unit_price or Decimal("0.00"),
                    width=130,
                ),
                Column(
                    "TOTAL",
                    lambda e: money(e.total_amount),
                    align="right",
                    sort_key=lambda e: e.total_amount,
                    width=140,
                ),
                Column("DATE", lambda e: date_time(e.created_at), sort_key=_spent_at, width=180),
            ],
            view_model,
            parent,
        )

        # Category names are a lookup for the table, not a list of their
        # own — fetched once per visit rather than per row.
        categories.rowsLoaded.connect(self._on_categories_loaded)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Categories are created on their own screen mid-session, so this
        # refreshes rather than loading only at construction.
        self._categories.load()

    def filter_options(self):
        return self._category_filters()

    def row_actions(self) -> tuple[RowAction, ...]:
        return (VIEW_ACTION,)

    def record_card(self, row) -> RecordCard:
        return expense_card(row, category=self._category_label(row))

    def summary(self, rows: list):
        return (("Spent", money(sum((e.total_amount for e in rows), Decimal("0.00")))),)

    def toolbar_extras(self) -> list[QWidget]:
        selector = PeriodSelector(self._period)
        selector.periodChanged.connect(self.reload)
        return [selector]

    def _category_filters(self) -> list[FilterOption]:
        """One entry per category, so "what did utilities cost this month"
        is a choice rather than a search. Rebuilt whenever the categories
        themselves change — they are created on their own screen."""
        options = []
        for category_id, name in sorted(self._category_names.items(), key=lambda kv: kv[1]):
            options.append(
                FilterOption(name, lambda e, wanted=category_id: e.category_id == wanted)
            )
        options.append(FilterOption("Uncategorised", lambda e: not e.category_id))
        return options

    def quick_add_fields(self):
        self._new_expense = line_edit("e.g. Electricity bill")
        self._new_category = combo(_NO_CATEGORY)
        self._new_amount = line_edit("Amount")
        return (
            QuickAddField(self._new_expense, 3),
            QuickAddField(self._new_category, 2),
            QuickAddField(self._new_amount, 1),
        )

    def build_quick_add(self) -> CreateExpenseCommand | None:
        name = self._new_expense.text().strip()
        if not name:
            self._new_expense.setFocus()
            return None
        amount = _positive_decimal(self._new_amount.text())
        if amount is None:
            self._new_amount.setFocus()
            return None
        # The strip records a flat amount. A quantity at a unit price is a
        # second decision, and the dialog is where a decision belongs.
        return CreateExpenseCommand(
            expense_name=name,
            amount=amount,
            category_id=self._new_category.currentData(),
        )

    def _category_label(self, expense) -> str:
        if not expense.category_id:
            return DASH
        return self._category_names.get(expense.category_id, DASH)

    def _on_categories_loaded(self, categories: list) -> None:
        self._category_names = {c.id: c.name for c in categories}
        self.set_filter_options(self._category_filters())
        refill(
            self._new_category,
            _NO_CATEGORY,
            sorted(
                ((name, category_id) for category_id, name in self._category_names.items()),
                key=lambda entry: entry[0],
            ),
        )
        self.table.refresh()

    def open_create_dialog(self) -> None:
        ExpenseDialog(self.view_model, self._category_names, parent=self).exec()


class ExpenseDialog(FormDialog):
    """
    An expense is either a flat amount or a quantity at a unit price — the
    use case accepts one or the other. The mode selector makes that choice
    explicit, rather than showing three fields at once and letting the
    backend reject the wrong combination.
    """

    _FLAT = "Total amount"
    _COMPUTED = "Quantity × unit price"

    def __init__(
        self,
        view_model: CollectionViewModel,
        category_names: dict[int, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title="Record expense",
            subtitle="Anything spent running the press — materials, utilities, repairs.",
            submit_label="Record expense",
            parent=parent,
        )
        self._view_model = view_model
        self.bind(view_model.itemCreated, view_model.errorOccurred)

        self._name = self.add_row("Expense", QLineEdit(), required=True)
        self._name.setPlaceholderText("e.g. Electricity bill, Ink cartridges")

        self._category = QComboBox()
        self._category.addItem(_NO_CATEGORY, None)
        for category_id, name in sorted(category_names.items(), key=lambda kv: kv[1]):
            self._category.addItem(name, category_id)
        self.add_row("Category", self._category)

        self._mode = QComboBox()
        self._mode.addItems([self._FLAT, self._COMPUTED])
        self._mode.currentTextChanged.connect(self._on_mode_changed)
        self.add_row("Amount as", self._mode)

        self._amount = self.add_row("Total amount", QLineEdit())
        self._amount.setPlaceholderText("0.00")

        self._quantity = ModernSpinBox()
        self._quantity.setRange(1, 1_000_000)
        self.add_row("Quantity", self._quantity)

        self._unit_price = self.add_row("Unit price", QLineEdit())
        self._unit_price.setPlaceholderText("0.00")

        self._remarks = self.add_row("Remarks", QTextEdit())
        self._remarks.setFixedHeight(60)

        self._on_mode_changed(self._FLAT)

    def _on_mode_changed(self, mode: str) -> None:
        flat = mode == self._FLAT
        self.set_row_visible(self._amount, flat)
        self.set_row_visible(self._quantity, not flat)
        self.set_row_visible(self._unit_price, not flat)

    def build_command(self) -> CreateExpenseCommand | None:
        name = self._name.text().strip()
        category_id = self._category.currentData()
        remarks = self._remarks.toPlainText().strip() or None

        if self._mode.currentText() == self._FLAT:
            amount = _positive_decimal(self._amount.text())
            if amount is None:
                self.reject_with("Enter a total amount greater than zero.", self._amount)
                return None
            return CreateExpenseCommand(
                expense_name=name,
                amount=amount,
                category_id=category_id,
                remarks=remarks,
            )

        unit_price = _positive_decimal(self._unit_price.text())
        if unit_price is None:
            self.reject_with("Enter a unit price greater than zero.", self._unit_price)
            return None
        return CreateExpenseCommand(
            expense_name=name,
            category_id=category_id,
            quantity=self._quantity.value(),
            unit_price=unit_price,
            remarks=remarks,
        )

    def submit_command(self, command: CreateExpenseCommand) -> None:
        self._view_model.create(command)


def _positive_decimal(text: str) -> Decimal | None:
    try:
        value = Decimal(text.strip())
    except (InvalidOperation, ValueError):
        return None
    return value if value > 0 else None
