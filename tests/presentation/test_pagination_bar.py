from __future__ import annotations

import pytest

from app.application.dto.queries import PageResult
from app.presentation.widgets.pagination_bar import PaginationBar


def _page(page: int, total: int, size: int = 100) -> PageResult:
    first = (page - 1) * size
    return PageResult(
        rows=list(range(first, min(first + size, total))),
        total=total,
        page=page,
        page_size=size,
    )


@pytest.fixture()
def bar(qt_app) -> PaginationBar:
    return PaginationBar()


def test_it_says_which_rows_these_are(bar):
    bar.set_page(_page(page=2, total=1240))

    assert bar._range.text() == "Showing 101–200"


def test_a_long_range_is_grouped_the_way_the_count_beside_it_is(bar):
    """These are real numbers now, and "Showing 1101-1200" is not a thing
    anybody reads at a glance."""
    bar.set_page(_page(page=12, total=1240))

    assert bar._range.text() == "Showing 1,101–1,200"


def test_the_first_page_cannot_go_back(bar):
    bar.set_page(_page(page=1, total=1240))

    assert not bar._first.isEnabled()
    assert not bar._previous.isEnabled()
    assert bar._next.isEnabled()
    assert bar._last.isEnabled()


def test_the_last_page_cannot_go_on(bar):
    bar.set_page(_page(page=13, total=1240))

    assert bar._first.isEnabled()
    assert bar._previous.isEnabled()
    assert not bar._next.isEnabled()
    assert not bar._last.isEnabled()


def test_a_list_that_fits_on_one_page_shows_no_bar_at_all(bar):
    """A dead row of greyed arrows under a twelve-row list is chrome that
    never earns its space."""
    bar.show()
    bar.set_page(_page(page=1, total=12))

    assert not bar.isVisible()


def test_a_list_that_does_not_fit_shows_one(bar):
    bar.show()
    bar.set_page(_page(page=1, total=1240))

    assert bar.isVisible()


def test_an_empty_list_says_nothing_rather_than_showing_a_range(bar):
    bar.set_page(_page(page=1, total=0))

    assert bar._range.text() == ""
    assert not bar.isVisible()


def test_the_buttons_ask_for_the_page_they_name(bar):
    asked: list[int] = []
    bar.pageRequested.connect(asked.append)
    bar.set_page(_page(page=5, total=1240))

    bar._first.click()
    bar._previous.click()
    bar._next.click()
    bar._last.click()

    assert asked == [1, 4, 6, 13]


def test_the_size_selector_shows_the_size_in_use_without_asking_again(bar):
    """Set from a result rather than by the user, so it must not read as a
    request — that would fetch the page a second time."""
    asked: list[int] = []
    bar.pageSizeChanged.connect(asked.append)

    bar.set_page(_page(page=1, total=1240, size=200))

    assert bar._size.currentData() == 200
    assert asked == []


def test_choosing_a_size_asks_for_it(bar):
    asked: list[int] = []
    bar.pageSizeChanged.connect(asked.append)

    bar._size.setCurrentIndex(bar._size.findData(500))

    assert asked == [500]
