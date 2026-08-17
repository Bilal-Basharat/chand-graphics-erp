from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.domain.entities.inventory_item import InventoryItem
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.new_sale_dialog import NewSaleDialog, unsellable_reason

# A sale cannot be written for stock that isn't there, and the shop finds
# that out either when it picks the item or after it has built the whole
# invoice. These pin the first: which items are refused, in what words,
# and — the part that is easy to get wrong — at which moments a shopkeeper
# is interrupted to be told.

OUT_OF_STOCK = InventoryItem(id=2, name="Black Ink Bottle", current_stock=0, minimum_stock=1)
AT_MINIMUM = InventoryItem(id=3, name="Glossy Card", current_stock=4, minimum_stock=10)
PLENTIFUL = InventoryItem(id=1, name="80 gsm Art Paper", current_stock=100, minimum_stock=5)


class _SalesViewModel(QObject):
    """As much of the sales view model as the dialog touches.

    Including the two searches its pickers run: the dialog is handed the
    first page of the catalogue and asks for the rest as it is typed into,
    so a stand-in without them is not the contract.
    """

    itemCreated = Signal(object)
    errorOccurred = Signal(str)
    catalogueSearched = Signal(object, str, list)
    partiesSearched = Signal(str, list)

    def __init__(self) -> None:
        super().__init__()
        self.searched: list[tuple] = []

    def search_catalogue(self, item_type, term: str) -> None:
        self.searched.append((item_type, term))

    def search_parties(self, term: str) -> None:
        self.searched.append(("parties", term))

    def create(self, command) -> None:  # pragma: no cover - never reached here
        raise AssertionError("no sale should be recorded by these tests")


class _Dialog:
    """A sale dialog whose warnings are collected instead of shown.

    `warn` opens a modal message box, which a test cannot dismiss.
    """

    def __init__(self, qt_app, *catalogue: InventoryItem) -> None:
        self.warnings: list[str] = []
        self.dialog = NewSaleDialog(
            _SalesViewModel(),
            customers=[],
            payment_methods=[],
            catalogues={ItemType.INVENTORY_ITEM: list(catalogue)},
            current_user_id=1,
        )
        self.dialog.warn = self.warnings.append

    def pick(self, row: int) -> None:
        """Choose the item on that row of the list, as clicking it does."""
        picker = self.dialog._picker._item
        picker.setCurrentIndex(row)
        picker.activated.emit(row)


# ------------------------------------------------------- what may be sold


def test_an_item_with_none_left_is_refused_as_out_of_stock():
    assert unsellable_reason(OUT_OF_STOCK, "Black Ink Bottle") == (
        "'Black Ink Bottle' is out of stock. Record a purchase to bring it "
        "back in before selling it."
    )


def test_an_item_at_its_minimum_is_refused_with_what_is_left():
    """Mirrors CreateSaleUseCase, which will not sell an item down to or
    below its minimum — and says how far down it is, since the shopkeeper's
    next move is to order more."""
    assert unsellable_reason(AT_MINIMUM, "Glossy Card") == (
        "'Glossy Card' is down to its minimum (4 left). Record a purchase to "
        "bring it back above its minimum before selling it."
    )


def test_an_item_above_its_minimum_is_sellable():
    assert unsellable_reason(PLENTIFUL, "80 gsm Art Paper") is None


# ------------------------------------------------------- when it is said


def test_picking_an_out_of_stock_item_says_so_at_once(qt_app):
    """Rather than after quantity, price and the rest of the invoice have
    been typed against an item that was never sellable."""
    form = _Dialog(qt_app, PLENTIFUL, OUT_OF_STOCK)

    form.pick(1)

    assert form.warnings == [unsellable_reason(OUT_OF_STOCK, OUT_OF_STOCK.name)]


def test_picking_an_item_that_is_in_stock_says_nothing(qt_app):
    form = _Dialog(qt_app, PLENTIFUL, OUT_OF_STOCK)

    form.pick(0)

    assert form.warnings == []


def test_picking_a_low_item_is_left_to_the_moment_it_is_added(qt_app):
    """It is still on the shelf, and interrupting every pick of it would
    train the shopkeeper to dismiss the box that also says "none left"."""
    form = _Dialog(qt_app, PLENTIFUL, AT_MINIMUM)

    form.pick(1)

    assert form.warnings == []


def test_opening_the_form_on_an_out_of_stock_item_says_nothing(qt_app):
    """The first row of the catalogue is not a choice anybody made, and
    being met by a warning on opening a form is how one gets ignored."""
    form = _Dialog(qt_app, OUT_OF_STOCK, PLENTIFUL)

    form.dialog.show()

    assert form.warnings == []


# --------------------------------------------------- and again on adding


def _add(form: _Dialog, row: int, quantity: int = 1) -> None:
    picker = form.dialog._picker
    picker._item.setCurrentIndex(row)
    picker._quantity.setValue(quantity)
    picker._unit_price.setText("250")
    picker.submit()


def test_an_out_of_stock_item_cannot_be_added(qt_app):
    form = _Dialog(qt_app, OUT_OF_STOCK)

    _add(form, 0)

    assert form.warnings == [unsellable_reason(OUT_OF_STOCK, OUT_OF_STOCK.name)]
    assert form.dialog.lines == []


def test_an_item_at_its_minimum_cannot_be_added(qt_app):
    form = _Dialog(qt_app, AT_MINIMUM)

    _add(form, 0)

    assert form.warnings == [unsellable_reason(AT_MINIMUM, AT_MINIMUM.name)]
    assert form.dialog.lines == []


def test_a_sellable_item_becomes_a_line(qt_app):
    form = _Dialog(qt_app, PLENTIFUL)

    _add(form, 0, quantity=3)

    assert form.warnings == []
    assert [(line.item_id, line.quantity) for line in form.dialog.lines] == [(1, 3)]


def test_more_than_is_on_the_shelf_is_refused(qt_app):
    """Across the whole invoice, not line by line: two lines of the same
    item add up to one draw on the same stock."""
    item = InventoryItem(id=9, name="Vinyl Roll", current_stock=5, minimum_stock=1)
    form = _Dialog(qt_app, item)

    _add(form, 0, quantity=4)
    _add(form, 0, quantity=4)

    assert form.warnings == [
        "Only 5 of 'Vinyl Roll' in stock, and this invoice already has 4."
    ]
    assert [line.quantity for line in form.dialog.lines] == [4]
