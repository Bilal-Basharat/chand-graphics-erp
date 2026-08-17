"""
Where a list screen currently is: which page, what was typed, what it is
sorted and filtered by.

Small, and deliberately knows nothing about Qt. Everything fiddly about
paging is the bookkeeping around these six values — that a new search
starts again at page one but turning a page does not, that a control
which "changed" to what it already was must not send the screen back to
the server, that a reply which arrives after a newer one has to be thrown
away — and none of it needs a widget or a running application to be
exercised.

Every mutator answers **whether anything actually changed**, and the
caller fetches only if it did. That is not an optimisation: a filter box
rebuilt on every visit restores its selection by label (see
`widgets/list_controls.py`), so without the question being asked, walking
onto a screen would refetch it and reset it to page one.
"""
from __future__ import annotations

from app.application.dto.queries import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class PageState:
    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        sort_field: str | None = None,
        sort_desc: bool = False,
    ) -> None:
        self.page = 1
        self.page_size = _sane_size(page_size)
        self.search = ""
        self.sort_field = sort_field
        self.sort_desc = sort_desc
        self.filter_value: str | None = None
        """Whichever choice the screen's filter box is on. Left as the
        label's own value: what it *means* is the view model's business,
        since only it knows whether that is a stock level or a category."""
        self._token = 0

    # ------------------------------------------------- what is being listed

    # Each of these narrows the list, so each starts again at the first
    # page. Staying on page seven of a list that has just become eleven
    # rows long is how a screen ends up blank with nothing to explain it.

    def set_search(self, term: str) -> bool:
        term = term.strip()
        if term == self.search:
            return False
        self.search = term
        self.page = 1
        return True

    def set_sort(self, field: str | None, desc: bool) -> bool:
        if (field, desc) == (self.sort_field, self.sort_desc):
            return False
        self.sort_field = field
        self.sort_desc = desc
        self.page = 1
        return True

    def set_filter(self, value: str | None) -> bool:
        if value == self.filter_value:
            return False
        self.filter_value = value
        self.page = 1
        return True

    def set_page_size(self, size: int) -> bool:
        size = _sane_size(size)
        if size == self.page_size:
            return False
        self.page_size = size
        self.page = 1
        return True

    # ------------------------------------------------------------- paging

    def go_to_page(self, page: int, page_count: int | None = None) -> bool:
        """Move to a page, as far as there is one to move to."""
        page = max(1, page)
        if page_count is not None:
            page = min(page, max(1, page_count))
        if page == self.page:
            return False
        self.page = page
        return True

    def reset_page(self) -> bool:
        return self.go_to_page(1)

    # ------------------------------------------------------------- replies

    # A request is answered on a worker thread and nothing can be called
    # back, so two requests in flight finish in whichever order they
    # finish. Without a token the *last to arrive* wins, which on a search
    # box means the screen settles on whatever was typed second-to-last.

    def next_token(self) -> int:
        self._token += 1
        return self._token

    def is_current(self, token: int) -> bool:
        return token == self._token

    # --------------------------------------------------------------- query

    def as_kwargs(self) -> dict:
        """The five fields every `PageQuery` carries, for a view model to
        build its own query around. The filter is not among them: it has a
        different name and type on every screen that has one."""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "search": self.search,
            "sort_field": self.sort_field,
            "sort_desc": self.sort_desc,
        }


def _sane_size(size: int) -> int:
    return min(max(1, size), MAX_PAGE_SIZE)
