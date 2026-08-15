from __future__ import annotations

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyleOptionViewItem

from app.domain.entities.inventory_item import InventoryItem
from app.domain.enums.item_type import ItemType
from app.presentation.widgets.item_picker_row import ItemDelegate, ItemPickerRow

# What the row is for is picking one item out of a shop's whole
# catalogue, so the cases pinned here are the ones that decide whether it
# can be: that a name can be found by any part of it, and that whatever
# ends up in the box is still one of the rows behind it — a picker that
# reports an item nobody chose is worse than one that is slow to scroll.


def _catalogue(*items: InventoryItem) -> dict[ItemType, list]:
    return {ItemType.INVENTORY_ITEM: list(items)}


@pytest.fixture()
def stock() -> dict[ItemType, list]:
    return _catalogue(
        InventoryItem(id=1, name="80 gsm Art Paper", current_stock=100, minimum_stock=5),
        InventoryItem(id=2, name="Black Ink Bottle", current_stock=0, minimum_stock=1),
        InventoryItem(id=3, name="Glossy Card 300gsm", current_stock=40, minimum_stock=10),
    )


@pytest.fixture()
def row(qt_app, stock) -> ItemPickerRow:
    return ItemPickerRow(stock)


def _matches(row: ItemPickerRow, typed: str) -> list[str]:
    """The names offered for what has been typed so far."""
    completer = row._item.completer()
    completer.setCompletionPrefix(typed)
    model = completer.completionModel()
    return [model.index(i, 0).data() for i in range(completer.completionCount())]


def _finish_typing(row: ItemPickerRow, typed: str) -> None:
    """Type into the box and move on, as leaving the field or pressing
    Enter does."""
    row._item.setEditText(typed)
    row._item.lineEdit().editingFinished.emit()


# ------------------------------------------------------------------ search


def test_an_item_is_found_by_any_part_of_its_name(row):
    """Starts-with would be no help to a shopkeeper who remembers the
    weight of a paper rather than the number it is filed under."""
    assert _matches(row, "gsm") == ["80 gsm Art Paper", "Glossy Card 300gsm"]


def test_searching_ignores_case(row):
    """Nobody types a catalogue's capitals."""
    assert _matches(row, "BLACK INK") == ["Black Ink Bottle"]


def test_a_search_that_matches_nothing_offers_nothing(row):
    assert _matches(row, "wedding cards") == []


def test_typing_a_name_in_full_selects_that_item(row):
    """However it was capitalised — the box is a way to reach a row, not a
    field with its own idea of what was meant."""
    _finish_typing(row, "black ink bottle")

    assert row._item.currentData() == 2
    assert row._item.currentText() == "Black Ink Bottle"


def test_text_that_names_no_item_is_put_back(row):
    """Left on screen it would claim a choice that was never made, and the
    row would go on to add whichever item was selected before it under a
    name nobody picked."""
    row._item.setCurrentIndex(2)
    _finish_typing(row, "80 gsm art pap")

    assert row._item.currentText() == "Glossy Card 300gsm"
    assert row._item.currentData() == 3


def test_the_box_arrives_with_its_choice_selected(qt_app, row):
    """Otherwise typing lands beside the name already in the box and
    searches for the two of them run together, which matches nothing."""
    row.show()
    row.activateWindow()
    QTest.qWaitForWindowExposed(row)
    row._item.setFocus()
    QTest.qWait(50)  # the selection is queued behind the focus

    assert row._item.lineEdit().selectedText() == "80 gsm Art Paper"
    row.close()


def test_a_line_is_added_under_the_selected_item_s_own_name(row):
    """Not under the text in the box, which can be half-typed towards
    something else at the moment the button is pressed."""
    added = []
    row.added.connect(added.append)

    row._item.setCurrentIndex(1)
    row._item.setEditText("black ink bot")
    row._unit_price.setText("250")
    row.submit()

    assert [(picked.item_id, picked.label) for picked in added] == [(2, "Black Ink Bottle")]


# ------------------------------------------------------------------ choosing


def test_what_is_selected_is_reported_as_the_row_is_built(row):
    """The quantity cap hangs off this, so it has to be answered for the
    item the row opens on and not only for one that gets chosen."""
    seen = []
    row.itemChanged.connect(lambda item_type, item_id: seen.append(item_id))

    row._item.setCurrentIndex(1)

    assert seen == [2]


def test_only_a_deliberate_pick_is_reported_as_chosen(row):
    """A caller that answers a choice with a message must not fire it at
    the row the form merely opened on."""
    chosen = []
    row.itemChosen.connect(lambda item_type, item_id: chosen.append(item_id))

    row._item.setCurrentIndex(1)
    assert chosen == []

    row._item.activated.emit(1)
    assert chosen == [2]


def test_an_empty_catalogue_offers_nothing_to_pick(qt_app):
    """And says so, rather than looking like a list that failed to load."""
    empty = ItemPickerRow(_catalogue())
    rejected = []
    empty.rejected.connect(rejected.append)

    empty.submit()

    assert empty._item.currentData() is None
    assert rejected == ["Choose an item to add."]


# ------------------------------------------------------------------ drawing


def _paint(row: ItemPickerRow, index_row: int) -> None:
    """Draw one row of the list the way the popup does."""
    delegate = ItemDelegate(row._item)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 240, 26)
    pixmap = QPixmap(240, 26)
    painter = QPainter(pixmap)
    try:
        delegate.paint(painter, option, row._item.model().index(index_row, 0))
    finally:
        painter.end()


def test_every_row_carries_what_is_in_stock(row):
    assert [
        row._item.itemData(i, Qt.ItemDataRole.UserRole + 1) for i in range(row._item.count())
    ] == [100, 0, 40]


def test_a_row_draws_with_its_stock_figure(row):
    _paint(row, 0)


def test_the_no_items_row_draws_without_one(qt_app):
    """It has no stock to report, and "Stock: None" beside it read as a
    bug rather than as an empty catalogue."""
    empty = ItemPickerRow(_catalogue())
    assert empty._item.itemData(0, Qt.ItemDataRole.UserRole + 1) is None
    _paint(empty, 0)
