"""
The master-data screens: cabinets, payment methods, customers, suppliers,
inventory items and expense categories.

All six are `CollectionView` subclasses, so what each one contributes is
just its copy, its columns, and which dialog its primary button opens.
They live together because they're read as a set — the shape of one tells
you the shape of the others.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateExpenseCategoryCommand,
    CreateInventoryItemCommand,
    CreatePaymentMethodCommand,
)
from app.presentation.dialogs.master_data_dialogs import (
    CabinetDialog,
    CustomerDialog,
    ExpenseCategoryDialog,
    InventoryItemDialog,
    PaymentMethodDialog,
    SupplierDialog,
)
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModel
from app.presentation.views.collection_view import CollectionPage, EditableCollectionView
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.quick_add_strip import QuickAddField, line_edit
from app.presentation.widgets.stock_status import (
    stock_filters,
    stock_status_color,
    stock_status_text,
)
from app.presentation.widgets.table_model import Column

_DASH = "—"


def _or_dash(value) -> str:
    return str(value) if value else _DASH


class CabinetsView(EditableCollectionView):
    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Items", "Cabinets"),
                title="Cabinets",
                subtitle="Physical storage locations that wedding cards are filed under.",
                panel_title="Cabinet list",
                empty_message="No cabinets yet. Add one to start filing cards.",
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
            "Cards filed under it are kept — they simply stop naming a cabinet.\n\n"
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


class CustomersView(EditableCollectionView):
    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Parties", "Customers"),
                title="Customers",
                subtitle="People and businesses you sell to. Attach one to a sale to track its balance.",
                panel_title="Customer list",
                empty_message="No customers yet. Add one, or record walk-in sales without a customer.",
                unit="customer",
                search_placeholder="Search customers by name",
                create_label="Add customer",
            ),
            [
                Column("NAME", lambda c: c.name),
                Column("PHONE", lambda c: _or_dash(c.phone), width=160),
                Column("ADDRESS", lambda c: _or_dash(c.address)),
                Column("NOTES", lambda c: _or_dash(c.notes)),
            ],
            view_model,
            parent,
        )

    def open_create_dialog(self) -> None:
        CustomerDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        CustomerDialog(self.view_model, customer=row, parent=self).exec()


class SuppliersView(EditableCollectionView):
    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Parties", "Suppliers"),
                title="Suppliers",
                subtitle="People and businesses you buy from. Attach one to a purchase to track its balance.",
                panel_title="Supplier list",
                empty_message="No suppliers yet. Add one to record purchases against them.",
                unit="supplier",
                search_placeholder="Search suppliers by name",
                create_label="Add supplier",
            ),
            [
                Column("NAME", lambda s: s.name),
                Column("PHONE", lambda s: _or_dash(s.phone), width=160),
                Column("ADDRESS", lambda s: _or_dash(s.address)),
                Column("NOTES", lambda s: _or_dash(s.notes)),
            ],
            view_model,
            parent,
        )

    def open_create_dialog(self) -> None:
        SupplierDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        SupplierDialog(self.view_model, supplier=row, parent=self).exec()


class InventoryItemsView(EditableCollectionView):
    def __init__(self, view_model: CollectionViewModel, parent: QWidget | None = None) -> None:
        super().__init__(
            CollectionPage(
                crumb=("Items", "Inventory items"),
                title="Inventory items",
                subtitle="Non-card stock such as paper, ink and packaging, with its own stock levels.",
                panel_title="Item list",
                empty_message="No inventory items yet. Add the materials you keep in stock.",
                unit="item",
                search_placeholder="Search items by name",
                create_label="Add item",
            ),
            [
                Column("NAME", lambda i: i.name, sort_key=lambda i: i.name.lower()),
                Column("DESCRIPTION", lambda i: _or_dash(i.description)),
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

    def filter_options(self):
        return stock_filters()

    def quick_add_fields(self):
        self._new_item = line_edit("e.g. A4 Ivory Sheet 250gsm")
        self._new_unit = line_edit("Unit, e.g. sheets")
        self._new_minimum = ModernSpinBox()
        self._new_minimum.setRange(0, 1_000_000)
        self._new_minimum.setPrefix("Min: ")
        return (
            QuickAddField(self._new_item, 3),
            QuickAddField(self._new_unit, 2),
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
            unit=self._new_unit.text().strip() or None,
        )

    def open_create_dialog(self) -> None:
        InventoryItemDialog(self.view_model, parent=self).exec()

    def open_edit_dialog(self, row) -> None:
        InventoryItemDialog(self.view_model, item=row, parent=self).exec()


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
