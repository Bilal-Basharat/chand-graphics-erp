from __future__ import annotations

import time

import pytest
from PySide6.QtTest import QTest

from app.application.dto.queries import PageQuery, PageResult
from app.presentation.viewmodels.collection_viewmodel import (
    CollectionSource,
    CollectionViewModel,
)

# The view model's side of paging: which reply it keeps, where it goes
# after a write, and what it does when the page it is on stops existing.
# Driven through a fake source rather than a database — what is under test
# is the state machine, not the query.


class _Catalogue:
    """A list of `total` rows, served a page at a time."""

    def __init__(self, total: int = 250) -> None:
        self.total = total
        self.asked: list[PageQuery] = []

    def page(self, query: PageQuery) -> PageResult:
        self.asked.append(query)
        first = query.offset
        # Rows carry the term they were fetched for, so a test can tell
        # which request a delivered page came from. The queries run on
        # worker threads and finish in any order, so the order they were
        # *recorded* in proves nothing.
        rows = [
            f"{query.search}:{index}"
            for index in range(first, min(first + query.page_size, self.total))
        ]
        return PageResult(
            rows=rows, total=self.total, page=query.page, page_size=query.page_size
        )


def _settle(qt_app, *, until=None, seconds: float = 10.0) -> None:
    """Let the worker threads finish.

    Waits for a condition rather than a fixed number of ticks: the pool is
    shared with the rest of the suite, so how long a fetch takes to come
    back is not this test's to predict.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qt_app.processEvents()
        QTest.qWait(20)
        if until is not None and until():
            break
    for _ in range(4):  # a moment more, in case a second reply follows
        qt_app.processEvents()
        QTest.qWait(20)


@pytest.fixture()
def catalogue() -> _Catalogue:
    return _Catalogue()


@pytest.fixture()
def view_model(qt_app, catalogue) -> CollectionViewModel:
    return CollectionViewModel(CollectionSource(page=catalogue.page))


def _pages(view_model) -> list:
    seen: list = []
    view_model.pageLoaded.connect(seen.append)
    return seen


# ------------------------------------------------------------------ paging


def test_a_page_is_delivered_with_the_whole_list_s_count(qt_app, view_model):
    seen = _pages(view_model)

    view_model.reload()
    _settle(qt_app, until=lambda: bool(seen))

    assert len(seen) == 1
    assert (seen[-1].page, len(seen[-1].rows), seen[-1].total) == (1, 100, 250)


def test_the_next_page_asks_for_the_next_page(qt_app, view_model, catalogue):
    seen = _pages(view_model)
    view_model.reload()
    _settle(qt_app, until=lambda: bool(seen))

    view_model.next_page()
    _settle(qt_app, until=lambda: seen[-1].page == 2)

    assert seen[-1].page == 2
    assert catalogue.asked[-1].offset == 100


def test_the_last_page_is_the_last_there_is(qt_app, view_model):
    seen = _pages(view_model)
    view_model.reload()
    _settle(qt_app, until=lambda: bool(seen))

    view_model.last_page()
    _settle(qt_app, until=lambda: seen[-1].page == 3)

    assert seen[-1].page == 3
    assert len(seen[-1].rows) == 50


def test_asking_past_the_end_asks_for_nothing(qt_app, view_model, catalogue):
    view_model.reload()
    _settle(qt_app, until=lambda: view_model.result is not None)
    before = len(catalogue.asked)

    view_model.go_to_page(99)
    _settle(qt_app, until=lambda: view_model.result.page == 3)

    # Clamped to the last page, which is not the one being shown, so one
    # request — and then nothing at all for a repeat of it.
    view_model.go_to_page(99)
    _settle(qt_app)

    assert len(catalogue.asked) == before + 1


# --------------------------------------------------------- stale replies


def test_a_reply_that_has_been_overtaken_is_thrown_away(qt_app, catalogue):
    """Two calls out at once finish in whichever order they finish. The
    screen has to settle on what was asked for last, not on what arrived
    last — on a search box those are routinely different."""
    view_model = CollectionViewModel(CollectionSource(page=catalogue.page))
    seen = _pages(view_model)

    view_model.set_search("a")
    view_model.set_search("ab")
    view_model.set_search("abc")
    _settle(qt_app, until=lambda: bool(seen))

    # One page delivered, and it is the newest question's answer — not
    # whichever of the three happened to come back last.
    assert len(seen) == 1
    assert seen[-1].rows[0].startswith("abc:")
    assert {query.search for query in catalogue.asked} == {"a", "ab", "abc"}


# ------------------------------------------------- writing, and what follows


def test_a_create_goes_back_to_the_first_page(qt_app, catalogue):
    """Where the new record sorts. A create that appears to do nothing
    because the row landed on page four reads as a create that failed."""
    created = []
    view_model = CollectionViewModel(
        CollectionSource(page=catalogue.page, create=lambda command: created.append(command))
    )
    view_model.reload()
    _settle(qt_app, until=lambda: view_model.result is not None)
    view_model.last_page()
    _settle(qt_app, until=lambda: view_model.result.page == 3)

    view_model.create("a new one")
    _settle(qt_app, until=lambda: bool(created) and catalogue.asked[-1].page == 1)

    assert created == ["a new one"]
    assert catalogue.asked[-1].page == 1


def test_a_delete_stays_on_the_page_it_happened_on(qt_app, catalogue):
    view_model = CollectionViewModel(
        CollectionSource(page=catalogue.page, delete=lambda entity_id: None)
    )
    view_model.reload()
    _settle(qt_app, until=lambda: view_model.result is not None)
    view_model.go_to_page(2)
    _settle(qt_app, until=lambda: view_model.result.page == 2)

    view_model.delete(7)
    _settle(qt_app, until=lambda: len(catalogue.asked) >= 3)

    assert catalogue.asked[-1].page == 2


def test_deleting_the_last_row_of_the_last_page_falls_back_to_a_real_one(qt_app):
    """Otherwise the screen sits on a page that no longer exists, showing
    nothing and explaining nothing."""
    catalogue = _Catalogue(total=101)
    view_model = CollectionViewModel(
        CollectionSource(page=catalogue.page, delete=lambda entity_id: None)
    )
    seen = _pages(view_model)
    view_model.reload()
    _settle(qt_app, until=lambda: bool(seen))
    view_model.last_page()  # page 2, holding one row
    _settle(qt_app, until=lambda: seen[-1].page == 2)

    catalogue.total = 100  # that row is deleted
    view_model.delete(101)
    _settle(qt_app, until=lambda: seen[-1].page == 1 and len(seen[-1].rows) == 100)

    assert seen[-1].page == 1
    assert len(seen[-1].rows) == 100


def test_the_fallback_happens_once_rather_than_chasing_itself(qt_app):
    """An empty list is an answer. Asking again for a page that cannot
    exist would be a loop, not a recovery."""
    catalogue = _Catalogue(total=0)
    view_model = CollectionViewModel(CollectionSource(page=catalogue.page))
    seen = _pages(view_model)

    view_model.reload()
    _settle(qt_app, until=lambda: bool(seen))

    assert len(catalogue.asked) == 1
    assert seen[-1].rows == []
