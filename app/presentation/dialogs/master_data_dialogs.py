"""
Create and edit dialogs for the master-data modules.

Grouped in one file because each is only its fields plus a command —
`FormDialog` owns the chrome, validation and submit lifecycle. Customers
and suppliers share `_PartyDialog`: their commands are field-for-field
identical, so the only real difference is the wording.

Editing reuses the same dialog rather than a parallel set of classes: the
fields are the same fields, and a second class per module would be the
same form twice, free to drift apart. `record` is what decides which mode
a dialog is in, and it is the only thing that does.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QComboBox, QLineEdit, QTextEdit, QWidget

from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateCustomerCommand,
    CreateExpenseCategoryCommand,
    CreateInventoryItemCommand,
    CreatePaymentMethodCommand,
    CreateSupplierCommand,
    UpdateCabinetCommand,
    UpdateCustomerCommand,
    UpdateExpenseCategoryCommand,
    UpdateInventoryItemCommand,
    UpdatePaymentMethodCommand,
    UpdateSupplierCommand,
)
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModel
from app.presentation.widgets.modern_spinbox import ModernSpinBox

_NO_CABINET = "— None —"


class _CollectionFormDialog(FormDialog):
    """A create-or-edit dialog backed by a `CollectionViewModel`.

    `record` decides which: absent means create, present means edit that
    record. It also decides the wording, and which success signal closes
    the dialog — binding the wrong one leaves a saved form sitting open.
    """

    def __init__(
        self,
        view_model: CollectionViewModel,
        *,
        noun: str,
        subtitle: str,
        record: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        editing = record is not None
        super().__init__(
            title=f"Edit {noun}" if editing else f"Add {noun}",
            subtitle=subtitle,
            submit_label="Save changes" if editing else f"Add {noun}",
            parent=parent,
        )
        self._view_model = view_model
        self._record = record
        self.bind(
            view_model.itemUpdated if editing else view_model.itemCreated,
            view_model.errorOccurred,
        )

    @property
    def is_edit(self) -> bool:
        return self._record is not None

    def submit_command(self, command: Any) -> None:
        if self._record is None:
            self._view_model.create(command)
        else:
            self._view_model.update(command)


def _optional(field: QLineEdit | QTextEdit) -> str | None:
    text = field.text() if isinstance(field, QLineEdit) else field.toPlainText()
    return text.strip() or None


class CabinetDialog(_CollectionFormDialog):
    def __init__(
        self,
        view_model: CollectionViewModel,
        *,
        cabinet: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="cabinet",
            subtitle="Cabinets are the physical storage locations stock is filed under.",
            record=cabinet,
            parent=parent,
        )
        self._code = self.add_row("Code", QLineEdit(), required=True)
        self._code.setPlaceholderText("e.g. A-01")
        self._description = self.add_row("Description", QLineEdit())

        if cabinet is not None:
            self._code.setText(cabinet.code)
            self._description.setText(cabinet.description or "")

    def build_command(self) -> CreateCabinetCommand | UpdateCabinetCommand:
        code = self._code.text().strip()
        description = _optional(self._description)
        if self._record is None:
            return CreateCabinetCommand(code=code, description=description)
        return UpdateCabinetCommand(id=self._record.id, code=code, description=description)


class PaymentMethodDialog(_CollectionFormDialog):
    def __init__(
        self,
        view_model: CollectionViewModel,
        *,
        method: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="payment method",
            subtitle="Payment methods appear in the payment dropdown on sales and purchases.",
            record=method,
            parent=parent,
        )
        self._name = self.add_row("Name", QLineEdit(), required=True)
        self._name.setPlaceholderText("e.g. Cash, Bank transfer, EasyPaisa")

        if method is not None:
            self._name.setText(method.name)

    def build_command(self) -> CreatePaymentMethodCommand | UpdatePaymentMethodCommand:
        name = self._name.text().strip()
        if self._record is None:
            return CreatePaymentMethodCommand(name=name)
        return UpdatePaymentMethodCommand(id=self._record.id, name=name)


class ExpenseCategoryDialog(_CollectionFormDialog):
    def __init__(
        self,
        view_model: CollectionViewModel,
        *,
        category: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="expense category",
            subtitle="Categories group expenses so reports can break spending down.",
            record=category,
            parent=parent,
        )
        self._name = self.add_row("Name", QLineEdit(), required=True)
        self._name.setPlaceholderText("e.g. Utilities, Rent, Maintenance")
        self._description = self.add_row("Description", QLineEdit())

        if category is not None:
            self._name.setText(category.name)
            self._description.setText(category.description or "")

    def build_command(self) -> CreateExpenseCategoryCommand | UpdateExpenseCategoryCommand:
        name = self._name.text().strip()
        description = _optional(self._description)
        if self._record is None:
            return CreateExpenseCategoryCommand(name=name, description=description)
        return UpdateExpenseCategoryCommand(
            id=self._record.id, name=name, description=description
        )


class InventoryItemDialog(_CollectionFormDialog):
    def __init__(
        self,
        view_model: CollectionViewModel,
        cabinet_names: dict[int, str],
        *,
        item: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="item",
            subtitle="Stock you keep and trade — paper, ink, packaging, anything counted.",
            record=item,
            parent=parent,
        )
        self._name = self.add_row("Name", QLineEdit(), required=True)
        self._name.setPlaceholderText("e.g. A4 Ivory Sheet 250gsm")

        self._unit = self.add_row("Unit", QLineEdit())
        self._unit.setPlaceholderText("e.g. sheets, ml, bottles")

        self._minimum_stock = ModernSpinBox()
        self._minimum_stock.setRange(0, 1_000_000)
        self.add_row("Minimum stock", self._minimum_stock)

        self._cabinet = QComboBox()
        self._cabinet.addItem(_NO_CABINET, None)
        for cabinet_id, code in sorted(cabinet_names.items(), key=lambda kv: kv[1]):
            self._cabinet.addItem(code, cabinet_id)
        self.add_row("Cabinet", self._cabinet)

        self._description = self.add_row("Description", QTextEdit())
        self._description.setFixedHeight(64)

        if item is not None:
            self._name.setText(item.name)
            self._unit.setText(item.unit or "")
            self._minimum_stock.setValue(item.minimum_stock)
            self._cabinet.setCurrentIndex(max(self._cabinet.findData(item.cabinet_id), 0))
            self._description.setPlainText(item.description or "")

        self.add_note(
            "Count stock in the smallest unit you use it in — buy a ream, record "
            "500 sheets — so a job can consume part of one.\n\n"
            "Stock isn't set here; it moves through purchases, sales, jobs and "
            "adjustments. Prices aren't either; they're recorded per transaction."
        )

    def build_command(self) -> CreateInventoryItemCommand | UpdateInventoryItemCommand:
        name = self._name.text().strip()
        minimum_stock = self._minimum_stock.value()
        description = _optional(self._description)
        cabinet_id = self._cabinet.currentData()
        unit = _optional(self._unit)
        if self._record is None:
            return CreateInventoryItemCommand(
                name=name,
                minimum_stock=minimum_stock,
                current_stock=0,
                description=description,
                cabinet_id=cabinet_id,
                unit=unit,
            )
        return UpdateInventoryItemCommand(
            id=self._record.id,
            name=name,
            minimum_stock=minimum_stock,
            description=description,
            cabinet_id=cabinet_id,
            unit=unit,
        )


class _PartyDialog(_CollectionFormDialog):
    """Shared form for customers and suppliers — same fields, same command shape."""

    def __init__(
        self,
        view_model: CollectionViewModel,
        *,
        noun: str,
        subtitle: str,
        record: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun=noun,
            subtitle=subtitle,
            record=record,
            parent=parent,
        )
        self._name = self.add_row("Name", QLineEdit(), required=True)
        self._phone = self.add_row("Phone", QLineEdit())
        self._address = self.add_row("Address", QLineEdit())
        self._notes = self.add_row("Notes", QTextEdit())
        self._notes.setFixedHeight(64)

        if record is not None:
            self._name.setText(record.name)
            self._phone.setText(record.phone or "")
            self._address.setText(record.address or "")
            self._notes.setPlainText(record.notes or "")

    def _fields(self) -> tuple[str, str | None, str | None, str | None]:
        return (
            self._name.text().strip(),
            _optional(self._phone),
            _optional(self._address),
            _optional(self._notes),
        )


class CustomerDialog(_PartyDialog):
    def __init__(
        self,
        view_model: CollectionViewModel,
        *,
        customer: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="customer",
            subtitle="Customers can be attached to a sale so its balance is tracked against them.",
            record=customer,
            parent=parent,
        )

    def build_command(self) -> CreateCustomerCommand | UpdateCustomerCommand:
        name, phone, address, notes = self._fields()
        if self._record is None:
            return CreateCustomerCommand(name=name, phone=phone, address=address, notes=notes)
        return UpdateCustomerCommand(
            id=self._record.id, name=name, phone=phone, address=address, notes=notes
        )


class SupplierDialog(_PartyDialog):
    def __init__(
        self,
        view_model: CollectionViewModel,
        *,
        supplier: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="supplier",
            subtitle=(
                "Suppliers can be attached to a purchase so its balance is tracked "
                "against them."
            ),
            record=supplier,
            parent=parent,
        )

    def build_command(self) -> CreateSupplierCommand | UpdateSupplierCommand:
        name, phone, address, notes = self._fields()
        if self._record is None:
            return CreateSupplierCommand(name=name, phone=phone, address=address, notes=notes)
        return UpdateSupplierCommand(
            id=self._record.id, name=name, phone=phone, address=address, notes=notes
        )