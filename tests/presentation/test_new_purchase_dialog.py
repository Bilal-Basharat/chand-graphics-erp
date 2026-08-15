from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.domain.entities.inventory_item import InventoryItem
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.new_purchase_dialog import NewPurchaseDialog

# A purchase is what puts stock back, so nothing about stock may refuse
# one — least of all the out-of-stock warning the sale form raises, which
# is exactly the item a purchase is being written for. It searches the
# same catalogue the same way; that is all the two forms share here.

OUT_OF_STOCK = InventoryItem(id=2, name="Black Ink Bottle", current_stock=0, minimum_stock=1)


class _PurchasesViewModel(QObject):
    itemCreated = Signal(object)
    errorOccurred = Signal(str)

    def create(self, command) -> None:  # pragma: no cover - never reached here
        raise AssertionError("no purchase should be recorded by these tests")


def _dialog(*catalogue: InventoryItem) -> tuple[NewPurchaseDialog, list[str]]:
    dialog = NewPurchaseDialog(
        _PurchasesViewModel(),
        suppliers=[],
        payment_methods=[],
        catalogues={ItemType.INVENTORY_ITEM: list(catalogue)},
        current_user_id=1,
    )
    warnings: list[str] = []
    dialog.warn = warnings.append
    return dialog, warnings


def test_an_item_with_none_left_is_what_a_purchase_is_for(qt_app):
    dialog, warnings = _dialog(OUT_OF_STOCK)
    picker = dialog._picker

    picker._item.setCurrentIndex(0)
    picker._item.activated.emit(0)
    picker._quantity.setValue(20)
    picker._unit_price.setText("180")
    picker.submit()

    assert warnings == []
    assert [(line.item_id, line.quantity) for line in dialog.lines] == [(2, 20)]


def test_the_item_list_is_searched_the_same_way_the_sale_form_searches_it(qt_app):
    dialog, _ = _dialog(
        InventoryItem(id=1, name="80 gsm Art Paper", current_stock=100),
        OUT_OF_STOCK,
    )

    completer = dialog._picker._item.completer()
    completer.setCompletionPrefix("art")

    assert completer.completionCount() == 1
    assert completer.completionModel().index(0, 0).data() == "80 gsm Art Paper"
