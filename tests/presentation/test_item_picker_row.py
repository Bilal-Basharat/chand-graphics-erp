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


# ------------------------------------------------------- searching the shop

# With a search callback the row stops being a list and becomes a
# question: what it offers is whatever came back for what was typed. Three
# things then have to hold, and each fails silently if it does not — the
# choice already made must survive a batch that does not contain it, an
# answer to an older question must not overwrite a newer one, and the
# stock figure beside a row must survive the row being replaced.


@pytest.fixture()
def asked() -> list[tuple]:
    return []


@pytest.fixture()
def searching(qt_app, stock, asked) -> ItemPickerRow:
    return ItemPickerRow(stock, search=lambda item_type, term: asked.append((item_type, term)))


def _items_in(row: ItemPickerRow) -> list[str]:
    return [row._item.itemText(i) for i in range(row._item.count())]


def test_the_row_asks_for_matches_once_typing_pauses(qt_app, searching, asked):
    asked.clear()
    searching._item.lineEdit().setText("gsm")
    searching._item.lineEdit().textEdited.emit("gsm")
    QTest.qWait(400)
    qt_app.processEvents()

    assert asked == [(ItemType.INVENTORY_ITEM, "gsm")]


def test_it_asks_for_the_opening_page_of_a_kind_it_switches_to(searching, asked):
    """A kind is a catalogue of its own, and the row opens on the start of
    it rather than on whatever the last kind's search returned."""
    asked.clear()
    searching._on_kind_changed(0)

    assert asked == [(ItemType.INVENTORY_ITEM, "")]


def test_what_came_back_is_what_can_be_picked(searching):
    searching.set_options(
        ItemType.INVENTORY_ITEM,
        [InventoryItem(id=9, name="Vinyl Roll", current_stock=12)],
        term=None,
    )

    assert "Vinyl Roll" in _items_in(searching)


def test_the_item_already_chosen_survives_a_search_that_excludes_it(searching):
    """Pick "Black Ink", type "paper", and the box must still answer Black
    Ink until something else is deliberately chosen — the line about to be
    added is built from what it answers."""
    searching._item.setCurrentIndex(1)
    assert searching._item.currentData() == 2

    searching.set_options(
        ItemType.INVENTORY_ITEM,
        [InventoryItem(id=9, name="Vinyl Roll", current_stock=12)],
        term=None,
    )

    assert searching._item.currentData() == 2
    assert "Black Ink Bottle" in _items_in(searching)


def test_an_answer_to_an_older_question_is_ignored(searching):
    """Two searches can be out at once. The box's own text is the question,
    so a batch answering a different one is not the answer to it."""
    searching._item.lineEdit().setText("vinyl")
    before = _items_in(searching)

    searching.set_options(
        ItemType.INVENTORY_ITEM,
        [InventoryItem(id=9, name="Vinyl Roll", current_stock=12)],
        term="gsm",
    )

    assert _items_in(searching) == before


# The row also drops a batch that came back for a kind it has since moved
# off — paper offered under "Ink" is a list nobody asked for. Not pinned
# here because it cannot be provoked with one kind registered; see
# `ItemPickerRow.set_options`, and `item_types.ITEM_KINDS` for what
# registering a second one involves.


def test_the_stock_figure_survives_a_refill(searching):
    """It is painted from a role on each row, and every batch rebuilds
    every row — including the one carried over from before it."""
    searching._item.setCurrentIndex(1)

    searching.set_options(
        ItemType.INVENTORY_ITEM,
        [InventoryItem(id=9, name="Vinyl Roll", current_stock=12)],
        term=None,
    )

    stocks = {
        searching._item.itemText(i): searching._item.itemData(i, Qt.ItemDataRole.UserRole + 1)
        for i in range(searching._item.count())
    }
    assert stocks["Vinyl Roll"] == 12
    assert stocks["Black Ink Bottle"] == 0


def _typing(row: ItemPickerRow, typed: str) -> None:
    """Leave the row where a shopkeeper mid-search leaves it: on screen,
    holding the focus, with a word in the box and no answer to it yet."""
    row.show()
    row.activateWindow()
    QTest.qWaitForWindowExposed(row)
    row._item.setFocus()
    QTest.qWait(50)  # the opening selection is queued behind the focus
    QTest.keyClicks(row._item.lineEdit(), typed)


def test_the_word_being_searched_for_survives_the_answer_to_it(qt_app, searching):
    """The whole of why searching read as doing nothing: every row of a
    batch is stamped with its stock figure, one of those rows is the one
    selected, and an editable combo re-reads its line edit whenever the
    selected row is touched. So the word typed was replaced by an item's
    name at the moment its own matches arrived."""
    _typing(searching, "gsm")

    searching.set_options(
        ItemType.INVENTORY_ITEM,
        [InventoryItem(id=9, name="120 gsm Poster Paper", current_stock=12)],
        term="gsm",
    )

    assert searching._item.lineEdit().text() == "gsm"
    assert "120 gsm Poster Paper" in _items_in(searching)
    searching.close()


def test_the_matches_that_arrive_are_the_ones_offered(qt_app, searching):
    """The list of matches is built on a keystroke, and the matches for
    that keystroke land a moment after it. Unless it is built again, what
    is on screen is the list from before the search."""
    _typing(searching, "vinyl")

    searching.set_options(
        ItemType.INVENTORY_ITEM,
        [InventoryItem(id=9, name="Vinyl Roll", current_stock=12)],
        term="vinyl",
    )

    completer = searching._item.completer()
    offered = [
        completer.completionModel().index(i, 0).data()
        for i in range(completer.completionCount())
    ]
    assert offered == ["Vinyl Roll"]
    searching.close()


def test_a_box_nobody_is_typing_into_reads_as_what_it_answers(row):
    """There is nothing half-typed to protect once the focus is elsewhere,
    and a box left blank over a real choice is a form that looks unfilled
    and adds a line anyway."""
    assert row._item.currentText() == "80 gsm Art Paper"
    assert row._item.currentData() == 1


def test_a_placeholder_row_is_never_lost_to_a_refill(qt_app):
    """"— choose a supplier —" going missing turns "nobody chosen" into
    whichever record happened to match, and the form accepts it."""
    from app.presentation.widgets.searchable_combo import SearchableComboBox

    combo = SearchableComboBox()
    combo.set_placeholder_item("— choose a supplier —", None)
    combo.set_options([("Packages Paper Mill", 1)])

    combo.set_options([("Ink World Karachi", 2)])

    assert combo.itemText(0) == "— choose a supplier —"
    assert combo.itemData(0) is None
