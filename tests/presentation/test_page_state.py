from __future__ import annotations

from app.application.dto.queries import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.presentation.viewmodels.page_state import PageState

# The bookkeeping every list screen runs on, and the only part of paging
# that can be exercised without a running application. What is pinned
# here is the three things that are easy to get subtly wrong: when a
# change sends the screen back to the first page, when a control that
# "changed" to what it already said must not ask for anything, and which
# of two replies in flight is the one to keep.


# ------------------------------------------------------- back to the start


def test_a_new_search_starts_at_the_first_page():
    """Page seven of a list is not a place to start reading a narrower
    one — often there is no page seven of it."""
    state = PageState()
    state.go_to_page(7)

    assert state.set_search("paper")
    assert state.page == 1


def test_sorting_filtering_and_resizing_all_start_again():
    for change in (
        lambda s: s.set_sort("name", True),
        lambda s: s.set_filter("out"),
        lambda s: s.set_page_size(50),
    ):
        state = PageState()
        state.go_to_page(4)
        assert change(state)
        assert state.page == 1


def test_turning_a_page_is_not_starting_again():
    state = PageState()
    state.set_search("paper")

    assert state.go_to_page(3)
    assert (state.page, state.search) == (3, "paper")


# ------------------------------------------------------------ no-op guards


def test_setting_a_control_to_what_it_already_said_asks_for_nothing():
    """Load-bearing, not an optimisation: a filter box rebuilt on every
    visit restores its choice by label, and without this the screen
    refetches and jumps back to page one each time it is walked onto."""
    state = PageState()
    state.set_filter("out")
    state.go_to_page(5)

    assert not state.set_filter("out")
    assert state.page == 5


def test_the_same_search_typed_again_asks_for_nothing():
    state = PageState()
    state.set_search("paper")

    assert not state.set_search("  paper  ")


def test_asking_for_the_page_already_shown_asks_for_nothing():
    state = PageState()
    assert not state.go_to_page(1)


def test_a_page_beyond_the_last_settles_on_the_last():
    state = PageState()

    assert state.go_to_page(99, page_count=4)
    assert state.page == 4


def test_a_page_below_the_first_settles_on_the_first():
    state = PageState()
    state.go_to_page(3)

    assert state.go_to_page(-2)
    assert state.page == 1


# ------------------------------------------------------------------ sizes


def test_a_page_size_is_kept_within_what_may_be_asked_for():
    """Past the ceiling a page stops being a screenful and becomes a way
    of asking for the table back."""
    assert PageState(page_size=10_000).page_size == MAX_PAGE_SIZE
    assert PageState(page_size=0).page_size == 1
    assert PageState().page_size == DEFAULT_PAGE_SIZE


# ------------------------------------------------------------- stale replies


def test_only_the_newest_request_is_still_wanted():
    """Two calls can be out at once and finish in either order. Without
    this the screen settles on whichever arrived last, which on a search
    box is whatever was typed second-to-last."""
    state = PageState()
    first = state.next_token()
    second = state.next_token()

    assert not state.is_current(first)
    assert state.is_current(second)


# --------------------------------------------------------------- the query


def test_the_state_reads_out_as_the_five_fields_a_query_carries():
    state = PageState()
    state.set_search("gsm")
    state.set_sort("name", True)
    state.go_to_page(3)

    assert state.as_kwargs() == {
        "page": 3,
        "page_size": DEFAULT_PAGE_SIZE,
        "search": "gsm",
        "sort_field": "name",
        "sort_desc": True,
    }


def test_the_filter_is_not_among_them():
    """It has a different name and a different type on every screen that
    has one, so turning it into a query is the view model's business."""
    state = PageState()
    state.set_filter("out")

    assert "filter" not in state.as_kwargs()
    assert state.filter_value == "out"
