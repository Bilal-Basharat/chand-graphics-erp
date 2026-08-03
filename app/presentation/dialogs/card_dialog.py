"""
Modal form for adding or correcting a wedding card.

Cards carry no price at all: purchase/selling price is only meaningful
per transaction (the same card is bought and sold at a different price
every time), so it lives on PurchaseItem/SaleItem.unit_price and never on
the card. Stock is absent for the same kind of reason — it is the running
result of purchases, sales and adjustments, not a field to type over.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QComboBox, QLineEdit, QTextEdit, QWidget

from app.application.dto.commands import CreateCardCommand, UpdateCardCommand
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.viewmodels.wedding_cards_viewmodel import WeddingCardsViewModel
from app.presentation.widgets.modern_spinbox import ModernSpinBox

_NO_CABINET = "— None —"


class CardDialog(FormDialog):
    def __init__(
        self,
        view_model: WeddingCardsViewModel,
        cabinet_names: dict[int, str],
        *,
        card: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        editing = card is not None
        super().__init__(
            title="Edit card" if editing else "Add card",
            subtitle="A wedding card design in the catalogue, filed under a cabinet.",
            submit_label="Save changes" if editing else "Add card",
            parent=parent,
        )
        self._view_model = view_model
        self._card = card
        self.bind(
            view_model.itemUpdated if editing else view_model.itemCreated,
            view_model.errorOccurred,
        )

        self._card_number = self.add_row("Card number", QLineEdit(), required=True)
        self._name = self.add_row("Name", QLineEdit())

        self._minimum_stock = ModernSpinBox()
        self._minimum_stock.setRange(0, 1_000_000)
        self.add_row("Minimum stock", self._minimum_stock)

        self._cabinet = QComboBox()
        self._cabinet.addItem(_NO_CABINET, None)
        for cabinet_id, code in sorted(cabinet_names.items(), key=lambda kv: kv[1]):
            self._cabinet.addItem(code, cabinet_id)
        self.add_row("Cabinet", self._cabinet)

        self._description = self.add_row("Description", QTextEdit())
        self._description.setFixedHeight(60)

        if card is not None:
            self._card_number.setText(card.card_number)
            self._name.setText(card.name or "")
            self._minimum_stock.setValue(card.minimum_stock)
            self._cabinet.setCurrentIndex(max(self._cabinet.findData(card.cabinet_id), 0))
            self._description.setPlainText(card.description or "")

        self.add_note(
            "Stock isn't set here — it moves through purchases, sales and stock "
            "adjustments. Prices aren't either; they're recorded per transaction."
        )

    def build_command(self) -> CreateCardCommand | UpdateCardCommand:
        card_number = self._card_number.text().strip()
        name = self._name.text().strip() or None
        minimum_stock = self._minimum_stock.value()
        cabinet_id = self._cabinet.currentData()
        description = self._description.toPlainText().strip() or None

        if self._card is None:
            return CreateCardCommand(
                card_number=card_number,
                name=name,
                minimum_stock=minimum_stock,
                current_stock=0,
                cabinet_id=cabinet_id,
                description=description,
            )
        return UpdateCardCommand(
            id=self._card.id,
            card_number=card_number,
            name=name,
            minimum_stock=minimum_stock,
            cabinet_id=cabinet_id,
            description=description,
        )

    def submit_command(self, command: CreateCardCommand | UpdateCardCommand) -> None:
        if self._card is None:
            self._view_model.create(command)
        else:
            self._view_model.update(command)
