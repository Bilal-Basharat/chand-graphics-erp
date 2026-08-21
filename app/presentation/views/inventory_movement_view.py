"""
Inventory movement screen: the stock register.

Every change to a count that no purchase or sale explains, newest first,
across the whole catalogue — with the item on the row and a search that
matches on its name, so "why is this item's count what it is?" is one
word typed rather than a picker to work through first.

It used to open on an empty table with an item picker in its toolbar,
because the query behind it could only answer for one item. That made
choosing an item a precondition of the screen rather than part of
recording a movement, and the create button had to refuse until one was
chosen — a rule nobody could see before breaking it.

Everything that moves stock outside a sale or a purchase is recorded
here, and each way of moving it is its own dialog. A correction or a
write-off is somebody at the shelf; a return reverses a document and has
to name it, and which document it names depends on which way the goods
are going. Sharing one form would mean six rows appearing and vanishing
on a dropdown, and a set of rules that only sometimes applied.

Returns are recorded from here and nowhere else. They used to also sit
as a button on every row of the sale and purchase lists, next to the one
that opens the record — close enough that a mis-click on a list being
read started a form that changes stock.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from app.application.dto.commands import InventoryMovementCommand
from app.application.dto.queries import MovementPageQuery, PageResult
from app.container import AppContainer
from app.domain.enums.item_type import ItemType
from app.domain.enums.movement_type import MovementType
from app.presentation.dialogs.record_movement_dialog import RecordMovementDialog
from app.presentation.dialogs.record_return_dialog import (
    PURCHASE_RETURNS,
    SALE_RETURNS,
    RecordReturnDialog,
)
from app.presentation.formatting import DASH, date_time, or_dash
from app.presentation.item_types import catalogue_key, item_names, search_catalogues
from app.presentation.theme import tokens as t
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.viewmodels.returns_viewmodel import (
    PurchaseReturnsViewModel,
    SaleReturnsViewModel,
)
from app.presentation.views.collection_view import CollectionPage, CollectionView
from app.presentation.widgets.list_controls import FilterOption
from app.presentation.widgets.table_model import Column


class InventoryMovementViewModel(CollectionViewModelBase):
    """
    Not a `CollectionViewModel`: the screen also searches the item
    catalogues for the dialog that records against them, and names the
    items its own rows point at.
    """

    cataloguesSearched = Signal(object, str, list)  # ItemType, term, records
    namesLoaded = Signal(object)
    """Names for the page just delivered have landed — the table redraws."""

    def __init__(self, container: AppContainer) -> None:
        super().__init__()
        self._container = container
        self._item_names: dict[tuple[ItemType, int], str] = {}

    def search_catalogue(self, item_type: ItemType, term: str) -> None:
        """Matches for what is being typed into the dialog's item picker.

        Asked for rather than filtered from a loaded catalogue: past
        whatever a catalogue was capped at, the item being looked for
        simply was not in the box.
        """
        self.run_async(
            lambda: search_catalogues(self._container, term)[ItemType(item_type)],
            on_success=lambda records: self.cataloguesSearched.emit(item_type, term, records),
        )

    def build_query(self) -> MovementPageQuery:
        return MovementPageQuery(
            **self._state.as_kwargs(),
            movement_type=self._state.filter_value,
        )

    def fetch(self, query: MovementPageQuery) -> PageResult:
        return self._container.page_inventory_movements_use_case().execute(query)

    def item_name(self, movement) -> str:
        """What moved. A dash only while the name is still on its way."""
        return self._item_names.get(catalogue_key(movement), DASH)

    def load_names_for(self, movements: list) -> None:
        """Fetch the names this page's rows point at, and nothing else.

        By id rather than by loading a catalogue — the shop's item list is
        as long as the shop is old, and none of it beyond these hundred
        rows has any bearing on the register.
        """
        wanted: dict[ItemType, set[int]] = {}
        for movement in movements:
            key = catalogue_key(movement)
            if key[1] and key not in self._item_names:
                wanted.setdefault(key[0], set()).add(key[1])
        if not wanted:
            return

        def fetch() -> dict:
            return {
                item_type: item_names(self._container, item_type, ids)
                for item_type, ids in wanted.items()
            }

        def _on_success(found: dict) -> None:
            for item_type, names in found.items():
                self._item_names.update(
                    {(item_type, item_id): name for item_id, name in names.items()}
                )
            self.namesLoaded.emit(found)

        self.run_async(fetch, on_success=_on_success)

    def create(self, command: InventoryMovementCommand) -> None:
        use_case = self._container.record_inventory_movement_use_case()

        def _on_success(movement) -> None:
            self.itemCreated.emit(movement)
            # Back to the first page: a movement is recorded now, and the
            # register reads newest first.
            self.reload_from_start()

        self.run_async(lambda: use_case.execute(command), on_success=_on_success)


class InventoryMovementView(CollectionView):
    def __init__(
        self,
        view_model: InventoryMovementViewModel,
        sale_returns_view_model: SaleReturnsViewModel,
        purchase_returns_view_model: PurchaseReturnsViewModel,
        parent: QWidget | None = None,
    ) -> None:
        self._movement_view_model = view_model
        # The two return dialogs this screen opens, in the order their
        # buttons sit in the header. One list, so a button cannot end up
        # opening the other one's form.
        self._returns = (
            (SALE_RETURNS, sale_returns_view_model),
            (PURCHASE_RETURNS, purchase_returns_view_model),
        )

        super().__init__(
            CollectionPage(
                crumb=("Items", "Inventory movement"),
                title="Inventory movement",
                panel_title="Movement history",
                empty_message="No stock movements recorded yet.",
                unit="movement",
                search_placeholder="Search by item, reference or reason",
                create_label="Record movement",
                # Named for who the goods move between: the shopkeeper
                # knows which of the two happened before reaching for a
                # button, and neither dialog can be mistaken for the other.
                secondary_create_labels=tuple(
                    kind.action_label for kind, _view_model in self._returns
                ),
            ),
            [
                # What moved comes first: the register is read down the
                # item column, and a type without an item beside it says
                # nothing about the shop.
                Column("ITEM", view_model.item_name, sort_field="item"),
                Column(
                    "TYPE",
                    lambda m: m.movement_type.value.title(),
                    sort_field="type",
                    width=130,
                ),
                Column(
                    "CHANGE",
                    _change_text,
                    align="right",
                    color=_change_color,
                    sort_field="quantity",
                    width=100,
                ),
                # Before is what After was one row ago; only one of the two
                # is a column the query can order by.
                Column("BEFORE", lambda m: or_dash(m.previous_stock), align="right", width=90),
                Column(
                    "AFTER",
                    lambda m: or_dash(m.resulting_stock),
                    align="right",
                    sort_field="stock",
                    width=90,
                ),
                # Which document moved the stock. Without it a return and
                # the sale it answers read as two unexplained swings.
                Column("SOURCE", lambda m: or_dash(m.reference_no), width=200),
                Column("REASON", lambda m: or_dash(m.reason)),
                Column("DATE", _moved_at_text, sort_field="occurred", width=170),
            ],
            view_model,
            parent,
        )

        # Names arrive after the rows that display them.
        view_model.namesLoaded.connect(lambda _names: self.table.refresh())
        # A return moves stock, so the register it was recorded from has
        # a new row to show.
        for _kind, returns in self._returns:
            returns.returnRecorded.connect(lambda _record: self.reload_from_start())
            returns.errorOccurred.connect(self._movement_view_model.errorOccurred)

    def filter_options(self):
        return [
            FilterOption(movement_type.value.title(), str(movement_type.value))
            for movement_type in MovementType
        ]

    def on_rows_loaded(self, rows: list) -> None:
        self._movement_view_model.load_names_for(rows)

    def open_create_dialog(self) -> None:
        RecordMovementDialog(self._movement_view_model, parent=self).exec()

    def open_secondary_dialog(self, index: int) -> None:
        kind, returns = self._returns[index]
        RecordReturnDialog(returns, kind, parent=self).exec()


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
