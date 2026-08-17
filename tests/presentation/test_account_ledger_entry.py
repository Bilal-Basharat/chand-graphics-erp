from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.presentation.views.account_ledger_view import (
    CUSTOMER_LEDGER_PAGE,
    AccountLedgerView,
    AccountLedgerViewModel,
)
from app.presentation.widgets.period_selector import PeriodSelection

# The way in from the Ledger button on a customer or supplier row. The
# picker on the ledger holds a page of names rather than every name, so the
# party arrived at is routinely not one of the rows in it — which is the
# whole of what these pin.


@dataclass(frozen=True, slots=True)
class _Party:
    id: int
    name: str


class _Ledger(AccountLedgerViewModel):
    """The screen's view model with the database taken out of it.

    `reload` is recorded rather than run: what these tests are about is
    which account the screen settles on and how often it asks for the
    statement, neither of which needs the statement itself.
    """

    def __init__(self, period: PeriodSelection) -> None:
        super().__init__(container=None, period=period)  # type: ignore[arg-type]
        self.reads = 0

    def reload(self) -> None:
        self.reads += 1


@pytest.fixture()
def parties() -> list[_Party]:
    # A page of the list, none of which is the party opened below: the
    # position every party past the first page is in.
    return [_Party(id=index, name=f"Adamjee Traders {index:02d}") for index in range(1, 51)]


@pytest.fixture()
def view(qt_app) -> AccountLedgerView:
    period = PeriodSelection()
    return AccountLedgerView(CUSTOMER_LEDGER_PAGE, _Ledger(period), period)


def test_a_party_outside_the_picker_s_page_is_still_the_one_opened(view, parties):
    """The bug this pins: the ledger looked the party up in the picker, got
    nothing back, and opened on nobody without saying so."""
    view.select_party(900, "Zeeshan Enterprises")

    assert view.view_model._party_id == 900
    assert view._party.currentText() == "Zeeshan Enterprises"
    assert view.view_model.reads == 1

    # And the page of names landing afterwards does not take it back.
    view._on_parties_loaded(parties)

    assert view.view_model._party_id == 900
    assert view._party.currentData() == 900


def test_the_placeholder_arriving_after_the_choice_does_not_displace_it(view, parties):
    """The names load off the UI thread, so "— choose a customer —" is
    added *after* the choice made on the customer list, not before it."""
    view.select_party(7, "Adamjee Traders 07")
    view._on_parties_loaded(parties)

    assert view._party.itemText(0) == CUSTOMER_LEDGER_PAGE.party_placeholder
    assert view._party.itemData(0) is None
    assert view._party.currentData() == 7


def test_a_party_inside_the_page_is_selected_rather_than_listed_twice(view, parties):
    view._on_parties_loaded(parties)
    before = view._party.count()

    view.select_party(7, "Adamjee Traders 07")

    assert view._party.count() == before
    assert view._party.currentData() == 7


def test_refilling_the_picker_does_not_re_read_the_statement(view, parties):
    """A statement is a period's worth of work. The names are refilled on
    every visit and after every keystroke, and none of that is a different
    account."""
    view.select_party(900, "Zeeshan Enterprises")
    read = view.view_model.reads

    view._on_parties_loaded(parties)
    view._on_parties_loaded(parties)

    assert view.view_model.reads == read
