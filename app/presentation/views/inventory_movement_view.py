"""
Inventory movement screen: the stock ledger for one item at a time.

The backend lists movements per card or per inventory item — there is no
"all movements" query — so the screen is built around picking an item and
reading its history, which is how a stock ledger is normally used anyway
("why is this card's count what it is?").

Recording a movement here covers only the exceptional cases the use case
allows: adjustment, damage, return and transfer. Purchase and sale stock
changes are recorded by those documents, not here.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QComboBox, QLineEdit, QTextEdit, QWidget

from app.application.dto.commands import InventoryMovementCommand
from app.container import AppContainer
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.formatting import card_label, date_time, or_dash
from app.presentation.theme import tokens as t
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.views.collection_view import CollectionPage, CollectionView
from app.presentation.widgets.item_type_combo import ItemTypeCombo
from app.presentation.widgets.list_controls import FilterOption
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.table_model import Column


class InventoryMovementViewModel(CollectionViewModelBase):
    """
    Not a `CollectionViewModel`: listing here is scoped to a selected item
    rather than being a whole-collection fetch, and the screen also needs
    the two catalogues to populate its picker.
    """

    catalogueLoaded = Signal(list, list)  # cards, inventory items

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container
        self._target: tuple[ItemType, int] | None = None

    def set_target(self, item_type: ItemType | None, item_id: int | None) -> None:
        self._target = (item_type, item_id) if item_type and item_id else None

    def load_catalogue(self) -> None:
        def fetch() -> tuple[list, list]:
            cards = self._container.list_cards_use_case().execute(500)
            items = self._container.list_inventory_items_use_case().execute(500)
            return cards, items

        self.run_async(fetch, on_success=lambda pair: self.catalogueLoaded.emit(*pair))

    def load(self) -> None:
        if self._target is None:
            # Nothing selected yet — an empty ledger, not an error.
            self.rowsLoaded.emit([])
            return

        item_type, item_id = self._target
        if item_type is ItemType.CARD:
            use_case = self._container.list_inventory_movements_by_card_use_case()
        else:
            use_case = self._container.list_inventory_movements_by_inventory_item_use_case()
        self.run_async(lambda: use_case.execute(item_id), on_success=self.rowsLoaded.emit)

    def search(self, term: str) -> None:  # noqa: ARG002 - scaffold contract, no text search here
        self.load()

    def create(self, command: InventoryMovementCommand) -> None:
        use_case = self._container.record_inventory_movement_use_case()

        def _on_success(movement) -> None:
            self.itemCreated.emit(movement)
            self.load()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)


class InventoryMovementView(CollectionView):
    def __init__(self, view_model: InventoryMovementViewModel, parent: QWidget | None = None) -> None:
        self._movement_view_model = view_model
        self._cards: list = []
        self._items: list = []

        super().__init__(
            CollectionPage(
                crumb=("Items", "Inventory movement"),
                title="Inventory movement",
                subtitle="The stock ledger — every exceptional change to an item's count, and why.",
                panel_title="Movement history",
                empty_message="Choose an item above to see its stock history.",
                unit="movement",
                create_label="Record movement",
            ),
            [
                Column("TYPE", lambda m: m.movement_type.value.title(), width=140),
                Column(
                    "CHANGE",
                    _change_text,
                    align="right",
                    color=_change_color,
                    sort_key=lambda m: m.quantity_change,
                    width=110,
                ),
                Column(
                    "BEFORE",
                    lambda m: or_dash(m.previous_stock),
                    align="right",
                    sort_key=lambda m: m.previous_stock or 0,
                    width=100,
                ),
                Column(
                    "AFTER",
                    lambda m: or_dash(m.resulting_stock),
                    align="right",
                    sort_key=lambda m: m.resulting_stock or 0,
                    width=100,
                ),
                # Which document moved the stock. Without it a job's
                # consumption and the return that answers it read as two
                # unexplained swings in the count.
                Column("SOURCE", lambda m: or_dash(m.reference_no), width=190),
                Column("REASON", lambda m: or_dash(m.reason)),
                Column("NOTE", lambda m: or_dash(m.note)),
                Column("DATE", _moved_at_text, sort_key=_moved_at, width=180),
            ],
            view_model,
            parent,
        )

        view_model.catalogueLoaded.connect(self._on_catalogue_loaded)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Cards and items are added on other screens during a session, so
        # the picker is refilled on each visit rather than at construction.
        self._movement_view_model.load_catalogue()

    def filter_options(self):
        return [
            FilterOption(
                movement_type.value.title(),
                lambda m, wanted=movement_type: m.movement_type is wanted,
            )
            for movement_type in MovementType
        ]

    def toolbar_extras(self) -> list[QWidget]:
        self._kind = ItemTypeCombo(card_label="Wedding cards", item_label="Inventory items")
        self._kind.currentIndexChanged.connect(self._on_kind_changed)

        self._item = QComboBox()
        self._item.setMinimumWidth(260)
        self._item.currentIndexChanged.connect(self._on_item_changed)

        return [self._kind, self._item]

    # ---------------- selection ----------------

    def _on_catalogue_loaded(self, cards: list, items: list) -> None:
        self._cards = cards
        self._items = items
        self._repopulate_items()

    def _on_kind_changed(self, _index: int) -> None:
        self._repopulate_items()

    def _repopulate_items(self) -> None:
        is_card = self._kind.is_card
        rows = self._cards if is_card else self._items

        self._item.blockSignals(True)
        self._item.clear()
        if not rows:
            self._item.addItem("— none available —", None)
        for row in rows:
            self._item.addItem(card_label(row) if is_card else row.name, row.id)
        self._item.blockSignals(False)
        self._on_item_changed(self._item.currentIndex())

    def _on_item_changed(self, _index: int) -> None:
        self._movement_view_model.set_target(self._kind.selected_type(), self._item.currentData())
        self.reload()

    def open_create_dialog(self) -> None:
        item_id = self._item.currentData()
        if item_id is None:
            self._movement_view_model.errorOccurred.emit(
                "Choose an item first — a movement is always recorded against one."
            )
            return
        RecordMovementDialog(
            self._movement_view_model,
            item_type=self._kind.selected_type(),
            item_id=item_id,
            item_label=self._item.currentText(),
            parent=self,
        ).exec()


def _moved_at(movement) -> datetime:
    """When a movement happened, falling back to when it was recorded — and
    never None, so it can be sorted on."""
    return movement.occurred_at or movement.created_at or datetime.min


def _moved_at_text(movement) -> str:
    return date_time(movement.occurred_at or movement.created_at)


def _change_text(movement) -> str:
    # The sign comes from the movement's own before/after counts, not from
    # its type — see InventoryMovement.quantity_change for why the type
    # cannot answer it.
    change = movement.quantity_change
    return f"{'+' if change >= 0 else '−'}{abs(change)}"


def _change_color(movement) -> str:
    return t.SUCCESS if movement.quantity_change >= 0 else t.DANGER


class RecordMovementDialog(FormDialog):
    def __init__(
        self,
        view_model: InventoryMovementViewModel,
        *,
        item_type: ItemType,
        item_id: int,
        item_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title="Record stock movement",
            subtitle=f"Adjusting stock for {item_label}.",
            submit_label="Record movement",
            parent=parent,
        )
        self._view_model = view_model
        self._item_type = item_type
        self._item_id = item_id
        self.bind(view_model.itemCreated, view_model.errorOccurred)

        self._type = QComboBox()
        for movement_type in MovementType:
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

        self._reason = self.add_row("Reason", QLineEdit())
        self._reason.setPlaceholderText("Why the count changed")

        self._reference = self.add_row("Reference", QLineEdit())
        self._note = self.add_row("Note", QTextEdit())
        self._note.setFixedHeight(60)

        self.add_note(
            "Purchases and sales move stock on their own — record here only the "
            "exceptions: corrections, damage, returns and transfers."
        )
        self._on_type_changed(self._type.currentIndex())

    def _on_type_changed(self, _index: int) -> None:
        # The use case rejects a positive DAMAGE, so don't offer the choice.
        movement_type = MovementType(self._type.currentData())
        if movement_type is MovementType.DAMAGE:
            self._direction.setCurrentIndex(1)
            self._direction.setEnabled(False)
        else:
            self._direction.setEnabled(True)

    def build_command(self) -> InventoryMovementCommand | None:
        movement_type = MovementType(self._type.currentData())
        reason = self._reason.text().strip()

        # Mirrors the use case's own rule, so the user is told before a
        # round trip rather than after one.
        if movement_type in (MovementType.DAMAGE, MovementType.ADJUSTMENT) and not reason:
            self.reject_with(
                f"A reason is required for {movement_type.value.title()} movements.",
                self._reason,
            )
            return None

        quantity_change = self._quantity.value() * self._direction.currentData()
        return InventoryMovementCommand(
            movement_type=movement_type,
            item_type=self._item_type,
            quantity_change=quantity_change,
            card_id=self._item_id if self._item_type is ItemType.CARD else None,
            inventory_item_id=None if self._item_type is ItemType.CARD else self._item_id,
            reference_no=self._reference.text().strip() or None,
            reason=reason or None,
            note=self._note.toPlainText().strip() or None,
        )

    def submit_command(self, command: InventoryMovementCommand) -> None:
        self._view_model.create(command)
