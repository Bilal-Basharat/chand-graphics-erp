"""
Recording a stock change no document explains.

Two of them: a count put right, and goods written off. Both are somebody
at the shelf saying "this is what is actually there", and both need the
same five answers — which item, which way, how many, why, and any note.

Returns are not here. A return reverses a document and has to say which
one, which makes it a different form with a different set of rules — see
`record_return_dialog.py`. Keeping them apart is what lets each of these
two dialogs have one job: this one never asks for an invoice number, and
that one never lets a quantity past what the invoice sold.

The item is chosen inside the dialog rather than on the screen behind it.
A movement is recorded against one item, so choosing it is part of
recording it; picked outside, the screen had to refuse the button until
something was selected, which is a rule nobody could see before breaking.
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLineEdit, QTextEdit, QWidget

from app.application.dto.commands import InventoryMovementCommand
from app.domain.enums.movement_type import MovementType
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.widgets.item_search_field import ItemSearchField
from app.presentation.widgets.modern_spinbox import ModernSpinBox

RECORDABLE = (MovementType.ADJUSTMENT, MovementType.DAMAGE)
"""What may be recorded here, and in which order it is offered.

`MovementType.RETURN` is deliberately absent: a return without a document
behind it is exactly the hole that let stock be returned that was never
sold.
"""


class RecordMovementDialog(FormDialog):
    def __init__(self, view_model, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Record stock movement",
            subtitle="A correction or a write-off — the changes no purchase or sale explains.",
            submit_label="Record movement",
            parent=parent,
        )
        self._view_model = view_model
        self.bind(view_model.itemCreated, view_model.errorOccurred)

        # The dialog does its own catalogue plumbing: it asks, and it
        # takes up the answers. Torn down with every other connection when
        # the dialog closes — see `FormDialog.done`.
        self._item = ItemSearchField()
        self._item.searchRequested.connect(view_model.search_catalogue)
        self._item.kindChanged.connect(lambda kind: view_model.search_catalogue(kind, ""))
        self._connect(view_model.cataloguesSearched, self._on_catalogue_searched)
        self.add_row("Item", self._item)

        self._type = QComboBox()
        for movement_type in RECORDABLE:
            self._type.addItem(movement_type.value.title(), movement_type)
        self._type.currentIndexChanged.connect(self._on_type_changed)
        self.add_row("Movement", self._type)

        self._direction = QComboBox()
        self._direction.addItem("Stock in (+)", 1)
        self._direction.addItem("Stock out (−)", -1)
        self.add_row("Direction", self._direction)

        self._quantity = ModernSpinBox()
        self._quantity.setRange(1, 1_000_000)
        self.add_row("Quantity", self._quantity)

        self._reason = self.add_row("Reason", QLineEdit(), required=True)
        self._reason.setPlaceholderText("Why the count changed")

        self._reference = self.add_row("Reference", QLineEdit())
        self._note = self.add_row("Note", QTextEdit())
        self._note.setFixedHeight(60)

        self.add_note(
            "Purchases and sales move stock on their own, and goods coming back are "
            "recorded against the invoice they came off. Record here only a count "
            "put right or stock written off."
        )
        self._on_type_changed(self._type.currentIndex())
        # Opens populated; typing into the box narrows it by asking again.
        view_model.search_catalogue(self._item.selected_type(), "")

    def _on_catalogue_searched(self, item_type, term: str, records: list) -> None:
        self._item.set_options(item_type, records, term=term or None)

    def _on_type_changed(self, _index: int) -> None:
        # The use case rejects a positive DAMAGE, so don't offer the choice.
        if MovementType(self._type.currentData()) is MovementType.DAMAGE:
            self._direction.setCurrentIndex(1)
            self._direction.setEnabled(False)
        else:
            self._direction.setEnabled(True)

    def build_command(self) -> InventoryMovementCommand | None:
        item_id = self._item.selected_id()
        if item_id is None:
            self.reject_with("Choose the item this movement is against.", self._item)
            return None

        # Reason is marked required above, which is the same rule the use
        # case applies — so the user is told before a round trip.
        return InventoryMovementCommand(
            movement_type=MovementType(self._type.currentData()),
            item_type=self._item.selected_type(),
            quantity_change=self._quantity.value() * self._direction.currentData(),
            inventory_item_id=item_id,
            reference_no=self._reference.text().strip() or None,
            reason=self._reason.text().strip(),
            note=self._note.toPlainText().strip() or None,
        )

    def submit_command(self, command: InventoryMovementCommand) -> None:
        self._view_model.create(command)
