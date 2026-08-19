from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtCore import QObject, Signal

from app.application.dto.queries import ReturnableDocument, ReturnableLine
from app.domain.enums.item_type import ItemType
from app.presentation.dialogs.record_return_dialog import (
    PURCHASE_RETURNS,
    SALE_RETURNS,
    RecordReturnDialog,
)

# The form is the last line of defence in front of rules the use case
# also enforces, and it is the only one a shopkeeper ever sees. What is
# pinned here is what the form itself decides: what it shows before a
# document is chosen, how much it will let past, what it collects when
# several things come back at once, and what it offers to refund before
# anybody touches the box.


def _line(line_id: int = 1, quantity: int = 40, returned: int = 0, price: str = "20.00",
          label: str = "A4 70gsm"):
    return ReturnableLine(
        line_id=line_id,
        item_type=ItemType.INVENTORY_ITEM,
        inventory_item_id=7,
        label=label,
        quantity=quantity,
        returned=returned,
        unit_price=Decimal(price),
    )


def _document(
    *lines: ReturnableLine,
    party_id: int | None = 5,
    paid: str = "0.00",
    balance: str = "800.00",
    refundable: str | None = None,
    reference: str = "INV-1",
    document_id: int = 1,
) -> ReturnableDocument:
    return ReturnableDocument(
        document_id=document_id,
        reference=reference,
        party_id=party_id,
        party_name="Ahmad Traders",
        lines=lines or (_line(),),
        paid_amount=Decimal(paid),
        balance_amount=Decimal(balance),
        refundable=Decimal(refundable if refundable is not None else paid),
    )


class _ReturnsViewModel(QObject):
    """As much of the returns view model as the dialog touches."""

    documentsSearched = Signal(str, list)
    documentResolved = Signal(object)
    returnRecorded = Signal(object)
    errorOccurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.searched: list[str] = []
        self.resolved: list[int] = []
        self.recorded: list = []

    def search_documents(self, term: str) -> None:
        self.searched.append(term)

    def resolve_document(self, document_id: int) -> None:
        self.resolved.append(document_id)

    def record_return(self, command) -> None:
        self.recorded.append(command)


@pytest.fixture()
def view_model(qt_app) -> _ReturnsViewModel:
    return _ReturnsViewModel()


def _dialog(view_model, kind=SALE_RETURNS) -> RecordReturnDialog:
    dialog = RecordReturnDialog(view_model, kind)
    dialog.warnings = []
    dialog.reject_with = lambda message, field=None: dialog.warnings.append(message)
    return dialog


def _add(dialog, line_id: int, quantity: int) -> None:
    """Choose a line and take it onto the return, the way the form is used."""
    dialog._line.setCurrentIndex(dialog._line.findData(line_id))
    dialog._quantity.setValue(quantity)
    dialog.add_line()


# ------------------------------------------------------ choosing the document


def test_opening_asks_for_the_first_page_of_documents(view_model):
    _dialog(view_model)

    assert view_model.searched == [""]


def test_no_document_is_shown_as_chosen_until_one_is(view_model):
    """The box would otherwise stand showing whichever invoice came back
    first, beside an empty list of items — which reads as an invoice that
    sold nothing."""
    dialog = _dialog(view_model)

    view_model.documentsSearched.emit("", [("INV-9", 9), ("INV-8", 8)])

    assert dialog._reference.currentText() == "— Choose an invoice —"
    assert dialog._reference.currentData() is None
    assert view_model.resolved == []


def test_the_chosen_document_is_what_the_box_reads(view_model):
    dialog = _dialog(view_model)
    view_model.documentsSearched.emit("", [("INV-9", 9), ("INV-1", 1)])

    view_model.documentResolved.emit(_document(_line()))

    assert dialog._reference.currentText() == "INV-1"
    assert dialog._line.count() == 1


def test_choosing_another_document_drops_what_was_staged(view_model):
    """Those lines belong to an invoice that is no longer on screen."""
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(_line(line_id=1)))
    _add(dialog, 1, 5)

    view_model.documentResolved.emit(
        _document(_line(line_id=2), reference="INV-2", document_id=2)
    )

    assert dialog._returning == []
    assert dialog._value.text() == "0.00"


def test_picking_the_document_already_showing_changes_nothing(view_model):
    """Qt reports a click on the standing choice like any other. Taken as
    a change it would fetch the invoice again and lose what was added."""
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(_line(line_id=1)))
    _add(dialog, 1, 5)
    view_model.resolved.clear()

    dialog._on_reference_chosen(dialog._reference.currentIndex())

    assert view_model.resolved == []
    assert [staged.quantity for staged in dialog._returning] == [5]


# ------------------------------------------------------------------ the cap


def test_the_quantity_cannot_be_taken_past_what_the_line_has_left(view_model):
    """Refused at the spinner rather than on submit: a shopkeeper should
    not be able to type a number that was never going to be accepted."""
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(_line(quantity=40, returned=15)))

    dialog._quantity.setValue(999)

    assert dialog._quantity.maximum() == 25
    assert dialog._quantity.value() == 25


def test_a_line_with_nothing_left_is_not_offered_at_all(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(_line(quantity=40, returned=40)))

    assert dialog._line.count() == 1
    assert dialog._line.currentData() is None
    assert dialog.build_command() is None
    assert dialog.warnings == ["Add what is coming back first."]


def test_each_line_says_how_much_of_it_is_left(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(
        _document(_line(line_id=1, quantity=40, returned=15), _line(line_id=2, quantity=10))
    )

    assert [dialog._line.itemText(i) for i in range(dialog._line.count())] == [
        "A4 70gsm — 25 of 40 left",
        "A4 70gsm — 10 of 10 left",
    ]


# ------------------------------------------------ several things at one time


def test_two_items_can_come_back_on_one_return(view_model):
    """The reported gap: choosing the second item used to lose the first."""
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(
        _document(
            _line(line_id=1, quantity=10, price="20.00", label="Narkinsss"),
            _line(line_id=2, quantity=10, price="30.00", label="Azm"),
        )
    )

    _add(dialog, 1, 10)
    _add(dialog, 2, 10)

    assert [(staged.label, staged.quantity) for staged in dialog._returning] == [
        ("Narkinsss", 10),
        ("Azm", 10),
    ]
    assert dialog._value.text() == "500.00"


def test_the_same_line_added_twice_is_one_line(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(_line(line_id=1, quantity=40)))

    _add(dialog, 1, 10)
    _add(dialog, 1, 5)

    assert [staged.quantity for staged in dialog._returning] == [15]


def test_what_is_already_staged_comes_off_the_cap(view_model):
    """Otherwise two goes at one line could together return more than it
    sold — each under the cap, the pair of them over it."""
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(_line(line_id=1, quantity=40)))
    _add(dialog, 1, 30)

    assert dialog._quantity.maximum() == 10

    _add(dialog, 1, 10)
    assert [staged.quantity for staged in dialog._returning] == [40]

    dialog.add_line()
    assert dialog.warnings == ["Everything that line has left is already on this return."]
    assert [staged.quantity for staged in dialog._returning] == [40]


def test_a_staged_line_can_be_taken_off_again(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(_line(line_id=1, quantity=40)))
    _add(dialog, 1, 10)

    dialog._remove_line(0)

    assert dialog._returning == []
    assert dialog._value.text() == "0.00"


def test_editing_a_staged_line_puts_it_back_in_the_picker(view_model):
    """Cheaper than a dialog to change one number, and the quantity lands
    back under the same cap it was added under."""
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(
        _document(_line(line_id=1, quantity=40), _line(line_id=2, quantity=10))
    )
    _add(dialog, 1, 12)
    _add(dialog, 2, 3)

    dialog._edit_line(0)

    assert [staged.quantity for staged in dialog._returning] == [3]
    assert dialog._line.currentData() == 1
    assert dialog._quantity.value() == 12


# ---------------------------------------------------------------- the refund


def test_an_unpaid_invoice_offers_no_refund(view_model):
    """The credit comes off what is still owed, which is what a credit
    customer expects — handing cash back would be paying twice."""
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(paid="0.00", balance="800.00"))

    _add(dialog, 1, 2)

    assert dialog._refund.text() == "0.00"
    assert dialog._method.isVisible() is False


def test_a_settled_invoice_offers_the_money_back(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(paid="800.00", balance="0.00"))

    _add(dialog, 1, 2)

    assert dialog._refund.text() == "40.00"


def test_a_walk_in_return_offers_the_money_back(view_model):
    """There is no account to carry the credit, so cash is the only way to
    make the customer whole."""
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(
        _document(party_id=None, paid="800.00", balance="0.00")
    )

    _add(dialog, 1, 2)

    assert dialog._refund.text() == "40.00"


def test_a_refund_is_never_offered_beyond_what_was_received(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(
        _document(party_id=None, paid="30.00", balance="0.00", refundable="30.00")
    )

    _add(dialog, 1, 2)

    assert dialog._refund.text() == "30.00"


def test_a_refund_above_the_value_of_the_goods_is_refused(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document(paid="800.00", balance="0.00"))
    _add(dialog, 1, 2)

    dialog._refund.setText("100.00")

    assert dialog.build_command() is None
    assert "cannot be more than the 40.00" in dialog.warnings[0]


def test_a_refund_above_what_was_received_is_refused(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(
        _document(paid="30.00", balance="0.00", refundable="30.00")
    )
    _add(dialog, 1, 2)

    dialog._refund.setText("40.00")

    assert dialog.build_command() is None
    assert "Only 30.00 has been received" in dialog.warnings[0]


# ---------------------------------------------------------------- the command


def test_the_command_names_every_line_the_goods_came_off(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(
        _document(
            _line(line_id=42, quantity=10),
            _line(line_id=43, quantity=10, price="30.00"),
            paid="800.00",
            balance="0.00",
        )
    )
    _add(dialog, 42, 3)
    _add(dialog, 43, 1)
    dialog._refund.setText("0.00")

    command = dialog.build_command()

    assert command.sale_id == 1
    assert [(line.line_id, line.quantity) for line in command.lines] == [(42, 3), (43, 1)]
    assert command.refund_amount == Decimal("0.00")
    # No method where no money moved.
    assert command.refund_method_id is None
    assert command.return_no.startswith("SR-")


def test_a_purchase_return_carries_the_other_document_id(view_model):
    dialog = _dialog(view_model, PURCHASE_RETURNS)
    view_model.documentResolved.emit(_document(_line(line_id=42)))
    _add(dialog, 42, 1)

    command = dialog.build_command()

    assert command.purchase_id == 1
    assert [line.line_id for line in command.lines] == [42]
    assert command.return_no.startswith("PR-")


def test_nothing_can_be_returned_before_a_document_is_chosen(view_model):
    dialog = _dialog(view_model)

    assert dialog.build_command() is None
    assert dialog.warnings == ["Choose the invoice these goods came off."]


def test_nothing_can_be_returned_until_something_is_added(view_model):
    dialog = _dialog(view_model)
    view_model.documentResolved.emit(_document())

    assert dialog.build_command() is None
    assert dialog.warnings == ["Add what is coming back first."]
