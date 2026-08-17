"""
View model for the "list, search, create" screens.

Cabinets, payment methods, customers, suppliers and inventory items differ
only in *which* use cases they call — the state machine around those calls
is identical. Rather than five near-identical view model classes, each
screen supplies a `CollectionSource` of callables and reuses this.

Screens whose listing genuinely differs — sales by period, movements for
one item, a report — subclass `CollectionViewModelBase` and answer one
question instead: given this page's query, what comes back.

A list is a page of a list. Nothing here ever asks for a whole table:
`PageState` says where the screen is, `build_query()` turns that into a
query the screen's own filters are added to, and `fetch()` answers it.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Signal

from app.application.dto.queries import DEFAULT_PAGE_SIZE, PageQuery, PageResult
from app.presentation.viewmodels.base import BaseViewModel
from app.presentation.viewmodels.page_state import PageState


@dataclass(frozen=True, slots=True)
class CollectionSource:
    """
    Each callable is invoked on a worker thread, so it should both build
    and execute its use case — that keeps the unit of work created and
    consumed on the same thread.
    """

    page: Callable[[PageQuery], PageResult]
    create: Callable[[Any], Any] | None = None
    update: Callable[[Any], Any] | None = None
    delete: Callable[[int], None] | None = None


class CollectionViewModelBase(BaseViewModel):
    """
    The contract `CollectionView` renders against.

    Most screens get it via `CollectionViewModel` below; the rest subclass
    this and implement `fetch`.
    """

    pageLoaded = Signal(object)  # PageResult
    itemCreated = Signal(object)
    itemUpdated = Signal(object)
    itemDeleted = Signal(int)

    def __init__(
        self,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        sort_field: str | None = None,
        sort_desc: bool = False,
    ) -> None:
        super().__init__()
        self._state = PageState(
            page_size=page_size, sort_field=sort_field, sort_desc=sort_desc
        )
        self._result: PageResult | None = None

    # ---------------- what a subclass answers ----------------

    def fetch(self, query: PageQuery) -> PageResult:
        """Run this screen's query. Called on a worker thread."""
        raise NotImplementedError

    def build_query(self) -> PageQuery:
        """Where the screen is, as a query.

        Screens with filters of their own override this to build their own
        `PageQuery` subclass around the same five fields — the filter's
        meaning is theirs, not the state's.
        """
        return PageQuery(**self._state.as_kwargs())

    # ---------------- what the screen asks for ----------------

    # Each of these fetches only if it changed something. A filter box or a
    # sort header that has been set to what it already said is not a
    # request for the same page a second time.

    def set_search(self, term: str) -> None:
        if self._state.set_search(term):
            self.reload()

    def set_sort(self, field: str | None, descending: bool) -> None:
        if self._state.set_sort(field, descending):
            self.reload()

    def set_filter(self, value: str | None) -> None:
        if self._state.set_filter(value):
            self.reload()

    def set_page_size(self, size: int) -> None:
        if self._state.set_page_size(size):
            self.reload()

    def open_sorted_by(self, field: str | None, descending: bool) -> None:
        """The order the list opens in.

        Sets the order without asking for anything: the screen is still
        being built and has not made a first request yet.
        """
        self._state.set_sort(field, descending)

    def open_filtered_by(self, value: str | None) -> None:
        """The filter the list opens narrowed to. Asks for nothing, for
        the same reason — otherwise a screen that opens on "not fully
        paid" fetches every document first and then throws it away."""
        self._state.set_filter(value)

    def go_to_page(self, page: int) -> None:
        if self._state.go_to_page(page, self.page_count):
            self.reload()

    def next_page(self) -> None:
        self.go_to_page(self._state.page + 1)

    def previous_page(self) -> None:
        self.go_to_page(self._state.page - 1)

    def first_page(self) -> None:
        self.go_to_page(1)

    def last_page(self) -> None:
        self.go_to_page(self.page_count)

    def reload(self) -> None:
        """Fetch the page the screen is on."""
        token = self._state.next_token()
        query = self.build_query()
        self.run_async(lambda: self.fetch(query), on_success=lambda r: self._arrived(token, r))

    def reload_from_start(self) -> None:
        """Fetch from page one — for a change to *what* is being listed
        rather than a refresh of it: another period, another item, another
        party. Staying on page seven of a different list shows nothing and
        explains nothing."""
        self._state.reset_page()
        self.reload()

    # ---------------- what came back ----------------

    @property
    def result(self) -> PageResult | None:
        """The last page delivered. `None` until the first one lands."""
        return self._result

    @property
    def page_count(self) -> int:
        return 1 if self._result is None else self._result.page_count

    @property
    def page_size(self) -> int:
        return self._state.page_size

    @property
    def search_term(self) -> str:
        """What is in the screen's search box, as the last fetch saw it."""
        return self._state.search

    @property
    def supports_editing(self) -> bool:
        """Whether rows can be edited and removed in place.

        Drives whether the list screen shows per-row actions at all — a
        column of buttons that always fail is worse than no column.
        """
        return False

    def emit_all(self, rows: list) -> None:
        """Deliver everything as a single page.

        For the screens whose answer is never a page — a statement, an
        ageing snapshot — whose figures are computed across the whole of
        it. They render through the same path as everything else, and the
        pagination bar simply finds one page to show.
        """
        rows = list(rows)
        self._arrived(
            self._state.next_token(),
            PageResult(rows=rows, total=len(rows), page=1, page_size=max(1, len(rows))),
        )

    def _arrived(self, token: int, result: PageResult) -> None:
        # A reply from a request that has since been superseded is thrown
        # away: two calls can be in flight at once and they finish in
        # whichever order they finish, so without this the screen settles
        # on whichever *arrived* last rather than what was last asked for.
        if not self._state.is_current(token):
            return

        # The page asked for is past the end — the last row of the last
        # page was just deleted. Ask again for the page that now exists.
        # `go_to_page` answers False once there is nowhere left to move,
        # so an empty list is delivered rather than chased forever.
        if not result.rows and result.total > 0 and self._state.go_to_page(result.page_count):
            self.reload()
            return

        self._result = result
        self.pageLoaded.emit(result)


class CollectionViewModel(CollectionViewModelBase):
    def __init__(
        self,
        source: CollectionSource,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        sort_field: str | None = None,
        sort_desc: bool = False,
    ) -> None:
        super().__init__(page_size=page_size, sort_field=sort_field, sort_desc=sort_desc)
        self._source = source

    def fetch(self, query: PageQuery) -> PageResult:
        return self._source.page(query)

    @property
    def supports_editing(self) -> bool:
        return self._source.update is not None and self._source.delete is not None

    def create(self, command: Any) -> None:
        create_fn = self._source.create
        if create_fn is None:
            raise RuntimeError("This collection is read-only — no create use case was supplied.")

        def _on_success(created: Any) -> None:
            self.itemCreated.emit(created)
            # Back to the first page, where a new record sorts: a create
            # that appears to do nothing because the row landed on page
            # four is the same bug report as a create that failed.
            self.reload_from_start()

        self.run_async(lambda: create_fn(command), on_success=_on_success)

    def update(self, command: Any) -> None:
        update_fn = self._source.update
        if update_fn is None:
            raise RuntimeError("This collection has no update use case.")

        def _on_success(updated: Any) -> None:
            self.itemUpdated.emit(updated)
            self.reload()

        self.run_async(lambda: update_fn(command), on_success=_on_success)

    def delete(self, entity_id: int) -> None:
        delete_fn = self._source.delete
        if delete_fn is None:
            raise RuntimeError("This collection has no delete use case.")

        def _on_success(_result: Any) -> None:
            self.itemDeleted.emit(entity_id)
            self.reload()

        self.run_async(lambda: delete_fn(entity_id), on_success=_on_success)
