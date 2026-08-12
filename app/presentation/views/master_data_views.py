"""
The master-data screens: cabinets, payment methods, customers, suppliers,
inventory and expense categories.

All six are `CollectionView` subclasses, so what each one contributes is
just its copy, its columns, and which dialog its primary button opens.
They live together because they're read as a set — the shape of one tells
you the shape of the others.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QWidget

from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateCustomerCommand,
    CreateExpenseCategoryCommand,
    CreateInventoryItemCommand,
    CreatePaymentMethodCommand,
    CreateSupplierCommand,
)
from app.presentation.dialogs.master_data_dialogs import (
    CabinetDialog,
    CustomerDialog,
    ExpenseCategoryDialog,
    InventoryItemDialog,
    PaymentMethodDialog,
    SupplierDialog,
)
from app.presentation.formatting import money
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModel
from app.presentation.viewmodels.master_data_viewmodels import InventoryViewModel
from app.presentation.views.collection_view import CollectionPage, EditableCollectionView
from app.presentation.widgets.input_validation import parse_balance, parse_phone
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.row_actions import RowAction
from app.presentation.widgets.quick_add_strip import (
    QuickAddField,
    combo,
    line_edit,
    money_edit,
    phone_edit,
    refill,
)
from app.presentation.widgets.stock_status import (
    stock_filters,
    stock_status_color,
    stock_status_text,
)
from app.presentation.widgets.table_model import Column

_DASH = "—"
_NO_CABINET = "— None —"

_LEDGER = "ledger"
_LEDGER_ACTION = RowAction(_LEDGER, "", icon="ledger", hint="Open this account's ledger")


def _or_dash(value) -> str:
    return str(value) if value else _DASH


class CabinetsView(EditableCollectionView):
    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Items", "Cabinets"),
                title="Cabinets",
                subtitle="Physical storage locations that stock is filed under.",
                panel_title="Cabinet list",
                empty_message="No cabinets yet. Add one to start filing stock.",
                unit="cabinet",
                create_label="Add cabinet",
            ),
            [
                Column("CODE", lambda c: c.code, width=180),
                Column("DESCRIPTION", lambda c: _or_dash(c.description)),
            ],
            view_model,
            parent,
        )

    def quick_add_fields(self):
        self._new_code = line_edit("Code, e.g. A-01")
        self._new_description = line_edit("Description")
        return (QuickAddField(self._new_code, 1), QuickAddField(self._new_description, 3))

    def build_quick_add(self) -> CreateCabinetCommand | None:
        code = self._new_code.text().strip()
        if not code:
            self._new_code.setFocus()
            return None
        return CreateCabinetCommand(
            code=code, description=self._new_description.text().strip() or None
        )

    def open_create_dialog(self) -> None:
        CabinetDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        CabinetDialog(self.view_model, cabinet=row, parent=self).exec()

    def describe(self, row) -> str:
        return f"cabinet {row.code}"

    def delete_warning(self, row) -> str:
        return (
            "Items filed under it are kept — they simply stop naming a cabinet.\n\n"
            "This cannot be undone."
        )


class PaymentMethodsView(EditableCollectionView):
    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Operations", "Payment methods"),
                title="Payment methods",
                subtitle="Ways money moves in and out besides cash — offered on every sale and purchase.",
                panel_title="Method list",
                empty_message="No payment methods yet. Payments record as cash until you add one.",
                unit="method",
                create_label="Add method",
            ),
            [Column("METHOD", lambda m: m.name)],
            view_model,
            parent,
        )

    def delete_warning(self, row) -> str:
        return (
            "Payments already recorded through it are kept, and read as cash.\n\n"
            "This cannot be undone."
        )

    def quick_add_fields(self):
        self._new_method = line_edit("e.g. Bank transfer, EasyPaisa, HBL")
        return (QuickAddField(self._new_method, 1),)

    def build_quick_add(self) -> CreatePaymentMethodCommand | None:
        name = self._new_method.text().strip()
        if not name:
            self._new_method.setFocus()
            return None
        return CreatePaymentMethodCommand(name=name)

    def open_create_dialog(self) -> None:
        PaymentMethodDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        PaymentMethodDialog(self.view_model, method=row, parent=self).exec()


class _PartyView(EditableCollectionView):
    """Customers and suppliers: the same list, and the same way in to an
    account.

    Both carry an opening balance and both have a ledger behind them, so
    the extra column, the extra row action and the quick-add row are
    stated once here. The screen that hosts it decides where the ledger
    lives — this only says which party was asked for.
    """

    ledgerRequested = Signal(int)

    quick_add_command: type[CreateCustomerCommand | CreateSupplierCommand]
    """What the quick-add row builds. The two commands are field-for-field
    identical — the same reason `_PartyDialog` is one class — so naming
    the type is the whole of the difference."""

    quick_add_placeholder: str
    """The example in the name box. Concrete, like every other strip in
    the app: "e.g. A4 Ivory Sheet 250gsm" tells you more than "Name"."""

    # ---------------- quick-add strip ----------------

    def quick_add_fields(self):
        # In the order the columns above read: who they are, how to reach
        # them, where they are, and what they already owed. Notes are the
        # one field left to the dialog — a note is a thought rather than a
        # keystroke, and it is the only one of the five nobody needs to
        # find a party again.
        self._new_name = line_edit(self.quick_add_placeholder)
        self._new_phone = phone_edit("Phone")
        self._new_address = line_edit("Address")
        self._new_opening = money_edit("Opening balance", signed=True)
        return (
            QuickAddField(self._new_name, 3),
            QuickAddField(self._new_phone, 2),
            QuickAddField(self._new_address, 3),
            QuickAddField(self._new_opening, 2),
        )

    def build_quick_add(self):
        name = self._new_name.text().strip()
        if not name:
            self._new_name.setFocus()
            return None

        phone = parse_phone(self._new_phone.text())
        if phone is None:
            self._new_phone.setFocus()
            self._new_phone.selectAll()
            return None

        opening_balance = parse_balance(self._new_opening.text())
        if opening_balance is None:
            self._new_opening.setFocus()
            self._new_opening.selectAll()
            return None

        return self.quick_add_command(
            name=name,
            phone=phone or None,
            address=self._new_address.text().strip() or None,
            opening_balance=opening_balance,
        )

    # ---------------- ledger ----------------

    def row_actions(self):
        # Before Edit and Remove: reading an account is the common,
        # harmless thing to do to a row, and the destructive one stays
        # last.
        return (_LEDGER_ACTION, *super().row_actions())

    def on_row_action(self, key: str, row) -> None:
        if key == _LEDGER:
            self.ledgerRequested.emit(row.id)
            return
        super().on_row_action(key, row)


class CustomersView(_PartyView):
    quick_add_command = CreateCustomerCommand
    quick_add_placeholder = "e.g. Ahmad Traders"

    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Parties", "Customers"),
                title="Customers",
                subtitle="People and businesses you sell to. Attach one to a sale to track its balance.",
                panel_title="Customer list",
                empty_message=(
                    "No customers yet. Add one in the row below, or record walk-in "
                    "sales without a customer."
                ),
                unit="customer",
                search_placeholder="Search customers by name",
                create_label="Add customer",
            ),
            [
                Column("NAME", lambda c: c.name),
                Column("PHONE", lambda c: _or_dash(c.phone), width=160),
                Column("ADDRESS", lambda c: _or_dash(c.address)),
                Column("NOTES", lambda c: _or_dash(c.notes)),
                Column(
                    "OPENING",
                    lambda c: money(c.opening_balance),
                    align="right",
                    sort_key=lambda c: c.opening_balance,
                    width=130,
                ),
            ],
            view_model,
            parent,
        )

    def open_create_dialog(self) -> None:
        CustomerDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        CustomerDialog(self.view_model, customer=row, parent=self).exec()


class SuppliersView(_PartyView):
    quick_add_command = CreateSupplierCommand
    quick_add_placeholder = "e.g. Paper Mill Co"

    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Parties", "Suppliers"),
                title="Suppliers",
                subtitle="People and businesses you buy from. Attach one to a purchase to track its balance.",
                panel_title="Supplier list",
                empty_message=(
                    "No suppliers yet. Add one in the row below to record purchases "
                    "against them."
                ),
                unit="supplier",
                search_placeholder="Search suppliers by name",
                create_label="Add supplier",
            ),
            [
                Column("NAME", lambda s: s.name),
                Column("PHONE", lambda s: _or_dash(s.phone), width=160),
                Column("ADDRESS", lambda s: _or_dash(s.address)),
                Column("NOTES", lambda s: _or_dash(s.notes)),
                Column(
                    "OPENING",
                    lambda s: money(s.opening_balance),
                    align="right",
                    sort_key=lambda s: s.opening_balance,
                    width=130,
                ),
            ],
            view_model,
            parent,
        )

    def open_create_dialog(self) -> None:
        SupplierDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        SupplierDialog(self.view_model, supplier=row, parent=self).exec()


class InventoryView(EditableCollectionView):
    def __init__(self, view_model: InventoryViewModel, parent: QWidget | None = None) -> None:
        self._inventory_view_model = view_model
        self._cabinet_names: dict[int, str] = {}

        super().__init__(
            CollectionPage(
                crumb=("Items", "Inventory"),
                title="Inventory",
                subtitle="Everything you keep in stock, where it is filed, and how much is left.",
                panel_title="Item list",
                empty_message="No items yet. Add one above, or use the quick-add row below.",
                unit="item",
                search_placeholder="Search items by name",
                create_label="Add item",
            ),
            [
                Column("NAME", lambda i: i.name, sort_key=lambda i: i.name.lower()),
                Column("DESCRIPTION", lambda i: _or_dash(i.description)),
                Column("CABINET", self._cabinet_label, width=150),
                Column("UNIT", lambda i: _or_dash(i.unit), width=110),
                Column(
                    "STOCK",
                    lambda i: i.current_stock,
                    align="right",
                    sort_key=lambda i: i.current_stock,
                    width=100,
                ),
                Column(
                    "MINIMUM",
                    lambda i: i.minimum_stock,
                    align="right",
                    sort_key=lambda i: i.minimum_stock,
                    width=110,
                ),
                Column(
                    "STATUS",
                    stock_status_text,
                    align="center",
                    color=stock_status_color,
                    sort_key=lambda i: i.current_stock,
                    width=130,
                ),
            ],
            view_model,
            parent,
        )

        view_model.cabinetsLoaded.connect(self._on_cabinets_loaded)

    def filter_options(self):
        return stock_filters()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Refreshed each visit rather than only when empty — cabinets get
        # added on their own screen, and a stale list here would silently
        # offer the wrong choices in the quick-add row and the dialog.
        self._inventory_view_model.load_cabinets()

    # ---------------- quick-add strip ----------------

    def quick_add_fields(self):
        self._new_item = line_edit("e.g. A4 Ivory Sheet 250gsm")
        self._new_unit = line_edit("Unit, e.g. sheets")
        self._new_cabinet = combo(_NO_CABINET)
        self._new_minimum = ModernSpinBox()
        self._new_minimum.setRange(0, 1_000_000)
        self._new_minimum.setPrefix("Min: ")
        return (
            QuickAddField(self._new_item, 3),
            QuickAddField(self._new_unit, 2),
            QuickAddField(self._new_cabinet, 2),
            QuickAddField(self._new_minimum, 1),
        )

    def build_quick_add(self) -> CreateInventoryItemCommand | None:
        name = self._new_item.text().strip()
        if not name:
            self._new_item.setFocus()
            return None
        return CreateInventoryItemCommand(
            name=name,
            minimum_stock=self._new_minimum.value(),
            current_stock=0,
            cabinet_id=self._new_cabinet.currentData(),
            unit=self._new_unit.text().strip() or None,
        )

    # ---------------- cabinets ----------------

    def _cabinet_label(self, item) -> str:
        if not item.cabinet_id:
            return _DASH
        return self._cabinet_names.get(item.cabinet_id, _DASH)

    def _on_cabinets_loaded(self, cabinets: list) -> None:
        self._cabinet_names = {c.id: c.code for c in cabinets}
        self.table.refresh()
        refill(
            self._new_cabinet,
            _NO_CABINET,
            sorted(
                ((code, cabinet_id) for cabinet_id, code in self._cabinet_names.items()),
                key=lambda entry: entry[0],
            ),
        )

    def open_create_dialog(self) -> None:
        InventoryItemDialog(self.view_model, self._cabinet_names, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        InventoryItemDialog(self.view_model, self._cabinet_names, item=row, parent=self).exec()


class ExpenseCategoriesView(EditableCollectionView):
    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Finance", "Expense categories"),
                title="Expense categories",
                subtitle="Groupings that let reports break spending down by kind.",
                panel_title="Category list",
                empty_message="No categories yet. Add one to start grouping expenses.",
                unit="category",
                unit_plural="categories",
                create_label="Add category",
            ),
            [
                Column("NAME", lambda c: c.name, width=240),
                Column("DESCRIPTION", lambda c: _or_dash(c.description)),
            ],
            view_model,
            parent,
        )

    def quick_add_fields(self):
        self._new_category = line_edit("e.g. Utilities, Rent, Maintenance")
        self._new_description = line_edit("Description")
        return (
            QuickAddField(self._new_category, 2),
            QuickAddField(self._new_description, 3),
        )

    def build_quick_add(self) -> CreateExpenseCategoryCommand | None:
        name = self._new_category.text().strip()
        if not name:
            self._new_category.setFocus()
            return None
        return CreateExpenseCategoryCommand(
            name=name, description=self._new_description.text().strip() or None
        )

    def open_create_dialog(self) -> None:
        ExpenseCategoryDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        ExpenseCategoryDialog(self.view_model, category=row, parent=self).exec()
