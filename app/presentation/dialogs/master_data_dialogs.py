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

from decimal import Decimal
from typing import Any

from PySide6.QtWidgets import QComboBox, QLineEdit, QTextEdit, QWidget

from app.application.dto.commands import (
    CreateCabinetCommand,
    CreateCategoryCommand,
    CreateProductCommand,
    CreateCustomerCommand,
    CreateExpenseCategoryCommand,
    CreateInventoryItemCommand,
    CreatePaymentMethodCommand,
    CreateSupplierCommand,
    UpdateCabinetCommand,
    UpdateCategoryCommand,
    UpdateCustomerCommand,
    UpdateExpenseCategoryCommand,
    UpdateInventoryItemCommand,
    UpdatePaymentMethodCommand,
    UpdateProductCommand,
    UpdateSupplierCommand,
)
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModel
from app.presentation.widgets.input_validation import (
    NOT_A_PHONE,
    ZERO,
    MoneyInput,
    PhoneInput,
    parse_balance,
    parse_phone,
)
from app.presentation.widgets.modern_spinbox import ModernDecimalSpinBox
from app.presentation.widgets.unit_rows import UnitRows

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
    """One stocked record: what it is called, what it is counted in, and
    what else it can be counted in.

    The same form whether it is the first item of its product or a second
    variant of one — `product_id` says which, and is the only difference
    between them. Nothing here says "SKU": for all but a handful of
    products this dialog is simply "the item".
    """

    def __init__(
        self,
        view_model: CollectionViewModel,
        cabinet_names: dict[int, str],
        *,
        item: Any | None = None,
        product_id: int | None = None,
        categories: dict[int, str] | None = None,
        category_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="item",
            subtitle="Stock you keep and trade — paper, ink, packaging, anything counted.",
            record=item,
            parent=parent,
        )
        self._product_id = product_id

        self._name = self.add_row("Name", QLineEdit(), required=True)
        self._name.setPlaceholderText("e.g. A4 Ivory Sheet 250gsm")

        # Only where this item is the only one of its product, which is
        # when the catalogue shows the two as one row: the form that edits
        # that row has to be able to change everything on it, and where it
        # is filed is on it. A variant has no shelf of its own — its
        # product does.
        self._category = None
        if categories:
            self._category = QComboBox()
            for shelf_id, shelf in sorted(categories.items(), key=lambda kv: kv[1]):
                self._category.addItem(shelf, shelf_id)
            self._category.setCurrentIndex(max(self._category.findData(category_id), 0))
            self.add_row("Category", self._category)

        self._unit = self.add_row("Unit", QLineEdit())
        self._unit.setPlaceholderText("e.g. sheets, ml, bottles")
        self._unit.textChanged.connect(lambda text: self._units.set_base_unit(text.strip()))

        self._minimum_stock = ModernDecimalSpinBox()
        self._minimum_stock.setRange(0, 1_000_000)
        self.add_row("Minimum stock", self._minimum_stock)

        self._cabinet = QComboBox()
        self._cabinet.addItem(_NO_CABINET, None)
        for cabinet_id, code in sorted(cabinet_names.items(), key=lambda kv: kv[1]):
            self._cabinet.addItem(code, cabinet_id)
        self.add_row("Cabinet", self._cabinet)

        self._description = self.add_row("Description", QTextEdit())
        self._description.setFixedHeight(64)

        self._units = UnitRows()
        self.add_row("Other units", self._units)

        if item is not None:
            self._name.setText(item.name)
            self._unit.setText(item.unit or "")
            self._minimum_stock.setValue(item.minimum_stock)
            self._cabinet.setCurrentIndex(max(self._cabinet.findData(item.cabinet_id), 0))
            self._description.setPlainText(item.description or "")
            self._units.set_base_unit(item.unit)

        self.add_note(
            "Count stock in the unit you keep it in — pieces, sheets, ml. Anything "
            "you also buy or sell it by goes under Other units: a Box worth 288 "
            "means buying ten boxes puts 2,880 on the shelf.\n\n"
            "Stock isn't set here; it moves through purchases, sales and "
            "adjustments. Prices aren't either; they're recorded per transaction."
        )

    def load_units(self, units) -> None:
        """Show the units this item already has, once they have arrived."""
        self._units.set_units(units)

    def build_command(self) -> CreateInventoryItemCommand | UpdateInventoryItemCommand | None:
        if self._units.units() is None:
            self.reject_with(
                "Give every other unit a name and how many of this item's own unit "
                "it is worth.",
                self._units.first_incomplete(),
            )
            return None

        name = self._name.text().strip()
        minimum_stock = self._minimum_stock.value()
        description = _optional(self._description)
        cabinet_id = self._cabinet.currentData()
        unit = _optional(self._unit)
        units = self._units.units() or ()
        if self._record is None:
            return CreateInventoryItemCommand(
                name=name,
                minimum_stock=minimum_stock,
                current_stock=0,
                description=description,
                cabinet_id=cabinet_id,
                unit=unit,
                product_id=self._product_id,
                units=units,
            )
        return UpdateInventoryItemCommand(
            id=self._record.id,
            name=name,
            minimum_stock=minimum_stock,
            description=description,
            cabinet_id=cabinet_id,
            unit=unit,
            units=units,
            category_id=self._category.currentData() if self._category else None,
        )


class CategoryDialog(_CollectionFormDialog):
    """A shelf in the catalogue. A name, and a line about what goes on it."""

    def __init__(
        self,
        view_model: CollectionViewModel,
        *,
        category: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="category",
            subtitle="How the catalogue is grouped — papers, inks, packaging.",
            record=category,
            parent=parent,
        )
        self._name = self.add_row("Name", QLineEdit(), required=True)
        self._name.setPlaceholderText("e.g. Papers")

        self._description = self.add_row("Description", QTextEdit())
        self._description.setFixedHeight(64)

        if category is not None:
            self._name.setText(category.name)
            self._description.setPlainText(category.description or "")

        self.add_note(
            "A category is only where a product is listed. Moving one between "
            "categories never touches its stock, its units or anything already "
            "bought or sold."
        )

    def build_command(self) -> CreateCategoryCommand | UpdateCategoryCommand:
        name = self._name.text().strip()
        description = _optional(self._description)
        if self._record is None:
            return CreateCategoryCommand(name=name, description=description)
        return UpdateCategoryCommand(id=self._record.id, name=name, description=description)


class ProductDialog(_CollectionFormDialog):
    """Something the shop trades in — and, the first time, the item under it.

    Creating one creates both: a product with nothing under it could not
    be bought, sold or counted. So the fields of the item are here too,
    and the shopkeeper adds one thing rather than two.

    Editing shows only what belongs to the product — its name and its
    shelf. Everything else is the item's, and a product with two variants
    has no single one of them to edit here.
    """

    def __init__(
        self,
        view_model: CollectionViewModel,
        categories: dict[int, str],
        cabinet_names: dict[int, str],
        *,
        product: Any | None = None,
        category_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            view_model,
            noun="product",
            subtitle="What you trade in — the name a customer would ask for.",
            record=product,
            parent=parent,
        )
        self._name = self.add_row("Name", QLineEdit(), required=True)
        self._name.setPlaceholderText("e.g. A4 Ivory 250gsm")

        self._category = QComboBox()
        for cid, name in sorted(categories.items(), key=lambda kv: kv[1]):
            self._category.addItem(name, cid)
        self.add_row("Category", self._category)

        if product is None:
            self._unit = self.add_row("Unit", QLineEdit())
            self._unit.setPlaceholderText("e.g. sheets, ml, bottles")

            self._minimum_stock = ModernDecimalSpinBox()
            self._minimum_stock.setRange(0, 1_000_000)
            self.add_row("Minimum stock", self._minimum_stock)

            self._cabinet = QComboBox()
            self._cabinet.addItem(_NO_CABINET, None)
            for cabinet_id, code in sorted(cabinet_names.items(), key=lambda kv: kv[1]):
                self._cabinet.addItem(code, cabinet_id)
            self.add_row("Cabinet", self._cabinet)

            self._description = self.add_row("Description", QTextEdit())
            self._description.setFixedHeight(64)

        if product is not None:
            self._name.setText(product.name)
            self._category.setCurrentIndex(max(self._category.findData(product.category_id), 0))
        elif category_id is not None:
            self._category.setCurrentIndex(max(self._category.findData(category_id), 0))

        self.add_note(
            "Most products are one thing counted one way, and that is all this "
            "asks for. Where a product really does come in two — matt and gloss, "
            "say — add the second from its row afterwards."
        )

    def build_command(self) -> CreateProductCommand | UpdateProductCommand:
        name = self._name.text().strip()
        if self._record is not None:
            return UpdateProductCommand(
                id=self._record.id,
                name=name,
                category_id=self._category.currentData(),
            )
        return CreateProductCommand(
            name=name,
            category_id=self._category.currentData(),
            unit=_optional(self._unit),
            minimum_stock=self._minimum_stock.value(),
            description=_optional(self._description),
            cabinet_id=self._cabinet.currentData(),
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
        self._phone = self.add_row("Phone", PhoneInput())
        self._address = self.add_row("Address", QLineEdit())

        # Signed, unlike every other money field: a negative opening
        # balance means the party is in credit.
        self._opening_balance = self.add_row(
            "Opening balance", MoneyInput(ZERO, signed=True)
        )

        self._notes = self.add_row("Notes", QTextEdit())
        self._notes.setFixedHeight(64)

        self.add_note(
            f"Opening balance is what this {noun} already owed before you started "
            "using this app. Leave it at 0 if nothing was outstanding."
        )

        if record is not None:
            self._name.setText(record.name)
            self._phone.setText(record.phone or "")
            self._address.setText(record.address or "")
            self._opening_balance.set_amount(record.opening_balance)
            self._notes.setPlainText(record.notes or "")

    def _fields(self) -> tuple[str, str | None, str | None, str | None, Decimal] | None:
        """This form's values, or None having pointed at what to fix."""
        phone = parse_phone(self._phone.text())
        if phone is None:
            self.reject_with(NOT_A_PHONE, self._phone)
            return None

        opening_balance = parse_balance(self._opening_balance.text())
        if opening_balance is None:
            self.reject_with(
                "Enter an opening balance as a number, or leave it blank for none.",
                self._opening_balance,
            )
            return None

        return (
            self._name.text().strip(),
            phone or None,
            _optional(self._address),
            _optional(self._notes),
            opening_balance,
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

    def build_command(self) -> CreateCustomerCommand | UpdateCustomerCommand | None:
        fields = self._fields()
        if fields is None:
            return None
        name, phone, address, notes, opening_balance = fields
        if self._record is None:
            return CreateCustomerCommand(
                name=name,
                phone=phone,
                address=address,
                notes=notes,
                opening_balance=opening_balance,
            )
        return UpdateCustomerCommand(
            id=self._record.id,
            name=name,
            phone=phone,
            address=address,
            notes=notes,
            opening_balance=opening_balance,
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

    def build_command(self) -> CreateSupplierCommand | UpdateSupplierCommand | None:
        fields = self._fields()
        if fields is None:
            return None
        name, phone, address, notes, opening_balance = fields
        if self._record is None:
            return CreateSupplierCommand(
                name=name,
                phone=phone,
                address=address,
                notes=notes,
                opening_balance=opening_balance,
            )
        return UpdateSupplierCommand(
            id=self._record.id,
            name=name,
            phone=phone,
            address=address,
            notes=notes,
            opening_balance=opening_balance,
        )