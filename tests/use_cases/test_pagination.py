from __future__ import annotations

from app.application.dto.commands import CreateCustomerCommand, CreateInventoryItemCommand
from app.application.dto.queries import (
    MAX_PAGE_SIZE,
    InventoryPageQuery,
    PageQuery,
)
from app.application.use_cases.inventory_items import (
    CreateInventoryItemUseCase,
    PageInventoryItemsUseCase,
)
from app.application.use_cases.master_data import (
    CreateCustomerUseCase,
    GetCustomerNamesUseCase,
    PageCustomersUseCase,
)
from app.domain.enums.stock_filter import StockFilter

# A page is only trustworthy if the pages either side of it agree with it.
# What is pinned here is that: every record appears exactly once across the
# pages, the order does not shuffle between them, the count describes the
# whole list rather than the page, and a search reaches records far past
# where the old fixed limits used to stop.

TOTAL = 250
"""Enough for three pages at the default size, and well past the fifty a
search used to be capped at."""


def _catalogue(uow, admin_session, count: int = TOTAL) -> None:
    create = CreateInventoryItemUseCase(uow, admin_session)
    for index in range(count):
        create.execute(
            CreateInventoryItemCommand(
                name=f"Item {index:04d}",
                minimum_stock=5 if index % 2 else 0,
                description="art paper" if index == count - 1 else None,
            )
        )


def _page(uow, admin_session, **kwargs) -> object:
    return PageInventoryItemsUseCase(uow, admin_session).execute(
        InventoryPageQuery(**kwargs)
    )


# ------------------------------------------------------------------ paging


def test_the_pages_together_are_the_whole_list_and_no_row_is_on_two(uow, admin_session):
    """The one thing a paged list has to get right. A record on two pages
    and another on none reads as data loss, not as a missing ORDER BY."""
    _catalogue(uow, admin_session)

    seen: list[int] = []
    for page in (1, 2, 3):
        result = _page(uow, admin_session, page=page, page_size=100)
        seen.extend(row.id for row in result.rows)

    assert len(seen) == TOTAL
    assert len(set(seen)) == TOTAL


def test_the_count_is_of_the_list_not_of_the_page(uow, admin_session):
    _catalogue(uow, admin_session)

    result = _page(uow, admin_session, page=2, page_size=100)

    assert len(result.rows) == 100
    assert result.total == TOTAL
    assert result.page_count == 3
    assert result.has_previous and result.has_next


def test_the_last_page_holds_what_is_left(uow, admin_session):
    _catalogue(uow, admin_session)

    result = _page(uow, admin_session, page=3, page_size=100)

    assert len(result.rows) == 50
    assert result.has_previous and not result.has_next
    assert (result.first_index, result.last_index) == (201, 250)


def test_a_page_past_the_end_is_empty_rather_than_an_error(uow, admin_session):
    """The screen clamps back to a real page when it sees this; the query
    itself has nothing to complain about."""
    _catalogue(uow, admin_session, count=10)

    result = _page(uow, admin_session, page=9, page_size=100)

    assert result.rows == []
    assert result.total == 10


def test_the_order_holds_across_pages_when_rows_tie(uow, admin_session):
    """Every record here sorts identically on the chosen column, so only
    the tiebreaker decides. Without one the database is free to answer
    page two in a different order to page one."""
    create = CreateInventoryItemUseCase(uow, admin_session)
    for index in range(30):
        create.execute(CreateInventoryItemCommand(name=f"Tied {index:03d}", minimum_stock=7))

    first = _page(uow, admin_session, page=1, page_size=10, sort_field="minimum")
    second = _page(uow, admin_session, page=2, page_size=10, sort_field="minimum")
    third = _page(uow, admin_session, page=3, page_size=10, sort_field="minimum")

    ids = [row.id for row in (*first.rows, *second.rows, *third.rows)]
    assert len(set(ids)) == 30


def test_a_page_is_never_bigger_than_the_ceiling(uow, admin_session):
    """A page is a screenful to read. Past the ceiling it is a way of
    asking for the table back, which is what this exists to stop."""
    _catalogue(uow, admin_session, count=10)

    result = _page(uow, admin_session, page=1, page_size=10_000)

    assert result.page_size == MAX_PAGE_SIZE


# ------------------------------------------------------------------ search


def test_a_search_reaches_records_past_the_first_page(uow, admin_session):
    """The whole point: the old ceilings meant a record at position 240
    could not be found at all."""
    _catalogue(uow, admin_session)

    result = _page(uow, admin_session, search="Item 0249")

    assert [row.name for row in result.rows] == ["Item 0249"]
    assert result.total == 1


def test_a_search_looks_beyond_the_name(uow, admin_session):
    _catalogue(uow, admin_session)

    result = _page(uow, admin_session, search="art paper")

    assert result.total == 1


def test_the_count_describes_the_search_not_the_catalogue(uow, admin_session):
    """A total left over from the unsearched list would give the screen a
    page count for records it is no longer showing."""
    _catalogue(uow, admin_session, count=30)

    result = _page(uow, admin_session, search="Item 001", page_size=5)

    assert result.total == 10
    assert result.page_count == 2


# ------------------------------------------------------------------ filters


def test_each_stock_filter_returns_what_its_label_claims(uow, admin_session):
    """A filter the query cannot express does not fail — it stays in the
    dropdown and quietly hands back everything."""
    create = CreateInventoryItemUseCase(uow, admin_session)
    create.execute(CreateInventoryItemCommand(name="Out of stock", minimum_stock=0))
    create.execute(CreateInventoryItemCommand(name="Below minimum", minimum_stock=5))

    out = _page(uow, admin_session, stock=StockFilter.OUT)
    low = _page(uow, admin_session, stock=StockFilter.LOW)
    stocked = _page(uow, admin_session, stock=StockFilter.IN)

    # Both are new, so both are at zero: one is out, and both are at or
    # below their minimum.
    assert out.total == 2
    assert low.total == 2
    assert stocked.total == 0


def test_a_filter_and_a_search_narrow_together(uow, admin_session):
    _catalogue(uow, admin_session, count=20)

    result = _page(uow, admin_session, search="Item 001", stock=StockFilter.OUT)

    assert result.total == 10


def test_an_unknown_sort_field_falls_back_rather_than_refusing(uow, admin_session):
    """A screen asking for an order this list does not offer gets the
    list's own order, not an exception in the middle of a page load."""
    _catalogue(uow, admin_session, count=5)

    result = _page(uow, admin_session, sort_field="nonsense")

    assert [row.name for row in result.rows] == [f"Item {i:04d}" for i in range(5)]


def test_sorting_runs_over_the_whole_list_not_the_page(uow, admin_session):
    """Sorted descending, the first page holds what would otherwise be the
    last — which is the difference between sorting a list and rearranging
    a screenful of it."""
    _catalogue(uow, admin_session, count=30)

    result = _page(uow, admin_session, page_size=5, sort_field="name", sort_desc=True)

    assert [row.name for row in result.rows] == [f"Item {i:04d}" for i in range(29, 24, -1)]


# ------------------------------------------------- the same shape elsewhere


def test_a_party_list_pages_and_searches_the_same_way(uow, admin_session):
    create = CreateCustomerUseCase(uow, admin_session)
    for index in range(120):
        create.execute(
            CreateCustomerCommand(name=f"Customer {index:04d}", phone=f"0300-100{index:04d}")
        )

    result = PageCustomersUseCase(uow, admin_session).execute(PageQuery(page=2, page_size=100))

    assert result.total == 120
    assert len(result.rows) == 20


def test_a_customer_is_found_by_the_number_they_ring_from(uow, admin_session):
    """A shop that knows a customer by their number has no other way to
    find them."""
    CreateCustomerUseCase(uow, admin_session).execute(
        CreateCustomerCommand(name="Al-Noor Printers", phone="0321-4567890")
    )

    result = PageCustomersUseCase(uow, admin_session).execute(PageQuery(search="4567890"))

    assert [row.name for row in result.rows] == ["Al-Noor Printers"]


def test_names_come_back_for_the_ids_asked_about(uow, admin_session):
    """What a document screen uses to name the rows on the page it is
    showing, rather than loading a table to look them up in."""
    create = CreateCustomerUseCase(uow, admin_session)
    first = create.execute(CreateCustomerCommand(name="Al-Noor Printers"))
    create.execute(CreateCustomerCommand(name="Someone Else"))

    names = GetCustomerNamesUseCase(uow, admin_session).execute([first.id])

    assert names == {first.id: "Al-Noor Printers"}


def test_asking_about_no_ids_asks_the_database_nothing(uow, admin_session):
    assert GetCustomerNamesUseCase(uow, admin_session).execute([]) == {}
