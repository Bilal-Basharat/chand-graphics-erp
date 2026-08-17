"""
Inventory movement screen: the stock ledger for one item at a time.

The backend lists movements per item — there is no "all movements" query
— so the screen is built around picking an item and reading its history,
which is how a stock ledger is normally used anyway ("why is this item's
count what it is?").

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
from app.application.dto.queries import MovementPageQuery, PageResult
from app.container import AppContainer
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.presentation.dialogs.form_dialog import FormDialog
from app.presentation.formatting import date_time, or_dash
from app.presentation.item_types import item_name, search_catalogues
from app.presentation.theme import tokens as t
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.views.collection_view import CollectionPage, CollectionView
from app.presentation.widgets.item_type_combo import ItemTypeCombo
from app.presentation.widgets.list_controls import FilterOption
from app.presentation.widgets.modern_spinbox import ModernSpinBox
from app.presentation.widgets.searchable_combo import SearchableComboBox
from app.presentation.widgets.table_model import Column


class InventoryMovementViewModel(CollectionViewModelBase):
    """
    Not a `CollectionViewModel`: listing here is scoped to a selected item
    rather than being a whole-collection fetch, and the screen also needs
    the item catalogues to populate its picker.
    """

    cataloguesSearched = Signal(object, str, list)  # ItemType, term, records

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container
        self._target: tuple[ItemType, int] | None = None

    def set_target(self, item_type: ItemType | None, item_id: int | None) -> None:
        self._target = (item_type, item_id) if item_type and item_id else None

    def search_catalogue(self, item_type: ItemType, term: str) -> None:
        """Matches for what is being typed into the item picker.

        Asked for rather than filtered from a loaded catalogue: past
        whatever a catalogue was capped at, the item whose history is
        being looked for simply was not in the box.
        """
        self.run_async(
            lambda: search_catalogues(self._container, term)[ItemType(item_type)],
            on_success=lambda records: self.cataloguesSearched.emit(item_type, term, records),
        )

    def build_query(self) -> MovementPageQuery:
        item_id = self._target[1] if self._target else 0
        return MovementPageQuery(
            **self._state.as_kwargs(),
            inventory_item_id=item_id,
            movement_type=self._state.filter_value,
        )

    def fetch(self, query: MovementPageQuery) -> PageResult:
        if self._target is None:
            # Nothing selected yet — an empty ledger, not an error.
            return PageResult.empty(query)
        # One "movements for this item" query per kind; a special item
        # module brings its own, chosen here on the selected type.
        return self._container.page_inventory_movements_use_case().execute(query)

    def create(self, command: InventoryMovementCommand) -> None:
        use_case = self._container.record_inventory_movement_use_case()

        def _on_success(movement) -> None:
            self.itemCreated.emit(movement)
            # Back to the first page: a movement is recorded now, and the
            # ledger reads newest first.
            self.reload_from_start()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)


class InventoryMovementView(CollectionView):
    def __init__(self, view_model: InventoryMovementViewModel, parent: QWidget | None = None) -> None:
        self._movement_view_model = view_model
        self._catalogues: dict[ItemType, list] = {}

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
                Column(
                    "TYPE",
                    lambda m: m.movement_type.value.title(),
                    sort_field="type",
                    width=140,
                ),
                Column(
                    "CHANGE",
                    _change_text,
                    align="right",
                    color=_change_color,
                    sort_field="quantity",
                    width=110,
                ),
                # Before is what After was one row ago; only one of the two
                # is a column the query can order by.
                Column("BEFORE", lambda m: or_dash(m.previous_stock), align="right", width=100),
                Column(
                    "AFTER",
                    lambda m: or_dash(m.resulting_stock),
                    align="right",
                    sort_field="stock",
                    width=100,
                ),
                # Which document moved the stock. Without it a job's
                # consumption and the return that answers it read as two
                # unexplained swings in the count.
                Column("SOURCE", lambda m: or_dash(m.reference_no), width=190),
                Column("REASON", lambda m: or_dash(m.reason)),
                Column("NOTE", lambda m: or_dash(m.note)),
                Column("DATE", _moved_at_text, sort_field="occurred", width=180),
            ],
            view_model,
            parent,
        )

        view_model.cataloguesSearched.connect(self._on_catalogue_searched)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        # Items are added on other screens during a session, so the picker
        # is refilled on each visit rather than at construction.
        self._movement_view_model.search_catalogue(self._kind.selected_type(), "")

    def filter_options(self):
        return [
            FilterOption(movement_type.value.title(), str(movement_type.value))
            for movement_type in MovementType
        ]

    def toolbar_extras(self) -> list[QWidget]:
        self._kind = ItemTypeCombo()
        self._kind.currentIndexChanged.connect(self._on_kind_changed)

        # Searched rather than scrolled: the item whose history is being
        # read is one name in a whole catalogue.
        self._item = SearchableComboBox()
        self._item.setToolTip("Type any part of an item's name to find it")
        self._item.setMinimumWidth(260)
        self._item.currentIndexChanged.connect(self._on_item_changed)
        self._item.searchRequested.connect(
            lambda term: self._movement_view_model.search_catalogue(
                self._kind.selected_type(), term
            )
        )

        return [self._kind, self._item]

    # ---------------- selection ----------------

    def _on_catalogue_searched(self, item_type, term: str, records: list) -> None:
        if ItemType(item_type) != self._kind.selected_type():
            return
        self._item.set_options(
            [(item_name(item_type, record), record.id) for record in records],
            term=term or None,
        )
        self._on_item_changed(self._item.currentIndex())

    def _on_kind_changed(self, _index: int) -> None:
        self._movement_view_model.search_catalogue(self._kind.selected_type(), "")

    def _on_item_changed(self, _index: int) -> None:
        self._movement_view_model.set_target(self._kind.selected_type(), self._item.currentData())
        # Another item is another ledger, not another page of this one.
        self.reload_from_start()

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
            inventory_item_id=self._item_id,
            reference_no=self._reference.text().strip() or None,
            reason=reason or None,
            note=self._note.toPlainText().strip() or None,
        )

    def submit_command(self, command: InventoryMovementCommand) -> None:
        self._view_model.create(command)
