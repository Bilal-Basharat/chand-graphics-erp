"""
The shared anatomy of every list screen.

Each module screen is: header, then a panel holding a toolbar and a table.
Subclasses declare their copy and columns via `CollectionPage`, and
override the hooks below for whatever is genuinely theirs (the create
dialog, extra filters, a footer strip). Nothing about layout, spacing,
search debouncing, loading state or error routing is restated per screen.

A screen shows one page of its list. Searching, filtering, sorting and
turning a page are all the same act — asking the view model for a
different page — so none of them is done to the rows in hand. Doing any
of it here would answer a question about the whole list using a hundredth
of it, and would look right while doing so.

Hooks, all optional:
    open_create_dialog()  - what the header's primary button does
    filter_options()      - the screen's Filter choices
    summary()             - the figures shown beside the panel title
    toolbar_leading()     - widgets at the start of the toolbar
    toolbar_extras()      - extra widgets placed left of Refresh
    quick_add_fields()    - an inline "add another" row under the table
    build_quick_add()     - the command that row submits
    build_footer()        - anything else pinned under the table
    create_table()        - the table widget itself, for lists that group
    row_actions()         - buttons drawn inside every row
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.application.dto.queries import PageResult
from app.presentation.dialogs.confirm import confirm_destructive
from app.presentation.dialogs.record_card_dialog import RecordCardDialog
from app.presentation.records.card import RecordCard
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.grouped_table import GroupedTable
from app.presentation.widgets.list_controls import FilterBox, FilterOption
from app.presentation.widgets.page_header import PageHeader
from app.presentation.widgets.pagination_bar import PaginationBar
from app.presentation.widgets.quick_add_strip import QuickAddField, QuickAddStrip
from app.presentation.widgets.row_actions import RowAction, RowActionsDelegate
from app.presentation.widgets.summary_strip import SummaryStrip
from app.presentation.widgets.table_model import Column

TableWidget = DataTable | GroupedTable
"""What a list screen renders into. Both expose the same small surface —
`set_rows`, `refresh`, `row_at`, `selected_row`, `set_placeholder` — so
everything below works against either."""

_SEARCH_DEBOUNCE_MS = 250

_EDIT = "edit"
_REMOVE = "remove"
_VIEW = "view"

VIEW_ACTION = RowAction(_VIEW, "", icon="view", hint="View the whole record")
"""The one action every document list carries, in the same place, drawn
the same way. A screen adds it to its `row_actions()` and answers
`record_card()`; the click is handled below, so no screen restates how a
card is opened.

An icon rather than the word "View": it appears on seven screens, several
of which already carry a worded button of their own, and a mark repeated
down every list stays quieter beside the record than a word would.
"""


@dataclass(frozen=True, slots=True)
class CollectionPage:
    crumb: tuple[str, ...]
    title: str
    panel_title: str
    empty_message: str
    unit: str
    """Noun for the record count, e.g. "customer" -> "12 customers"."""
    unit_plural: str | None = None
    search_placeholder: str | None = None
    create_label: str | None = None
    secondary_create_labels: tuple[str, ...] = ()
    """Other things this screen records, beside its primary action.

    Only the stock register has any: a correction, a customer return and
    a return to a supplier are three unrelated forms, and folding them
    into one would mean half the rows appearing and vanishing on a
    dropdown. They sit before the primary action and are drawn as
    outlines, so which one is primary stays obvious.

    Screens that set them answer `open_secondary_dialog`, by position.
    """

    quick_add_label: str | None = None
    """Wording on the inline row's button. Defaults to "Add"."""

    def count_label(self, count: int) -> str:
        if count == 1:
            return f"1 {self.unit}"
        plural = self.unit_plural or f"{self.unit}s"
        # Grouped: this counts a whole list now rather than a screenful,
        # and "1240 sales" is a number nobody reads at a glance.
        return f"{count:,} {plural}"


class CollectionView(QWidget):
    def __init__(
        self,
        page: CollectionPage,
        columns: Sequence[Column],
        view_model: CollectionViewModelBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._page = page
        self._view_model = view_model
        self._search: QLineEdit | None = None
        self._filter: FilterBox | None = None
        self._loaded_once = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        self._header = PageHeader(page.crumb, page.title)
        # Secondary actions first, so the primary one keeps the trailing
        # edge — see `PageHeader.add_action`.
        for index, label in enumerate(page.secondary_create_labels):
            self._header.add_action(
                label, lambda *_, at=index: self.open_secondary_dialog(at)
            )
        if page.create_label:
            self._header.add_action(page.create_label, self.open_create_dialog, variant="primary")
        outer.addWidget(self._header)

        outer.addWidget(self._build_panel(columns), 1)

        view_model.pageLoaded.connect(self._on_page_loaded)
        view_model.busyChanged.connect(self._on_busy_changed)
        view_model.errorOccurred.connect(self._on_error)

    # ---------------- construction ----------------

    def _build_panel(self, columns: Sequence[Column]) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        # 1px inset so the table's square bottom edge stops short of the
        # panel's rounded corners instead of painting over them.
        layout.setContentsMargins(1, 0, 1, 1)
        layout.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(18, 12, 18, 10)
        title_row.setSpacing(22)
        title = QLabel(self._page.panel_title)
        title.setProperty("role", "panelTitle")
        self._count_label = QLabel("")
        self._count_label.setProperty("role", "panelSub")
        # The screen's own figures sit with its title, not down among the
        # controls: they describe the list, they don't change it.
        self._summary = SummaryStrip()
        self._summary.hide()
        title_row.addWidget(title)
        title_row.addStretch(1)
        # Count first, then the figures: the boxes finish the row against
        # the panel edge, lined up with the Refresh button below them.
        title_row.addWidget(self._count_label)
        title_row.addWidget(self._summary)
        layout.addLayout(title_row)

        # Refresh sits with the list it refreshes, not up in the header
        # beside the page's primary action.
        refresh = QPushButton("Refresh")
        refresh.setProperty("variant", "outline")
        refresh.clicked.connect(self.reload)

        filters = self.filter_options()
        if filters:
            self._filter = FilterBox(filters)
            self._filter.changed.connect(self._on_filter_changed)

        leading = self.toolbar_leading()
        extras = self.toolbar_extras()
        if self._page.search_placeholder or leading or extras or self._filter is not None:
            layout.addLayout(self._build_toolbar(leading, extras, refresh))
        else:
            # Nothing else would share the row — a toolbar holding only
            # Refresh reads as an empty band under the title.
            title_row.addSpacing(12)
            title_row.addWidget(refresh)

        self._table = self._build_table(columns)
        layout.addWidget(self._table, 1)

        self._quick_add = self._build_quick_add()
        if self._quick_add is not None:
            layout.addWidget(self._quick_add)

        # Below the quick-add row, which reads as the table's last line.
        self._pagination = PaginationBar(self._view_model.page_size)
        self._pagination.pageRequested.connect(self._view_model.go_to_page)
        self._pagination.pageSizeChanged.connect(self._view_model.set_page_size)
        layout.addWidget(self._pagination)

        footer = self.build_footer()
        if footer is not None:
            layout.addWidget(footer)

        return panel

    def _build_quick_add(self) -> QuickAddStrip | None:
        fields = self.quick_add_fields()
        if not fields:
            return None
        strip = QuickAddStrip(fields, button_label=self._page.quick_add_label or "Add")
        strip.submitted.connect(self._submit_quick_add)
        # Cleared only once the record actually exists: emptying the row on
        # submit would lose what the user typed if the create were refused.
        self._view_model.itemCreated.connect(lambda _created: strip.reset())
        return strip

    def _submit_quick_add(self) -> None:
        command = self.build_quick_add()
        if command is not None:
            self._view_model.create(command)

    def _build_table(self, columns: Sequence[Column]) -> TableWidget:
        actions = self.row_actions()
        columns = list(columns)
        delegate = RowActionsDelegate(actions) if actions else None
        if delegate is not None:
            # Unlabelled: a heading over two buttons names nothing they
            # don't already say. Its width is measured from the labels, so
            # renaming an action can't leave a magic number behind.
            columns.append(Column("", lambda _row: "", width=delegate.column_width()))

        table = self.create_table(columns)
        # Sorting lives on the headings, and orders the whole list rather
        # than the page on screen — so a click asks for the list again in
        # that order rather than rearranging the hundred rows in hand.
        table.sorting.changed.connect(self._on_sort_changed)
        if delegate is not None:
            delegate.setParent(table)
            delegate.attach(table, column=len(columns) - 1)
            delegate.triggered.connect(self._on_row_action)
        return table

    def _on_row_action(self, key: str, row_index: int) -> None:
        row = self._table.row_at(row_index)
        if row is None:
            return
        # Handled here rather than passed on, so a screen that shows cards
        # says only what is on them.
        if key == _VIEW:
            self.show_record_card(row)
            return
        self.on_row_action(key, row)

    def show_record_card(self, row: object) -> None:
        card = self.record_card(row)
        if card is not None:
            RecordCardDialog(card, parent=self).exec()

    def _build_toolbar(
        self, leading: list[QWidget], extras: list[QWidget], refresh: QPushButton
    ) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(18, 0, 18, 12)
        toolbar.setSpacing(8)

        if self._page.search_placeholder:
            self._search_timer = QTimer(self)
            self._search_timer.setSingleShot(True)
            self._search_timer.setInterval(_SEARCH_DEBOUNCE_MS)
            self._search_timer.timeout.connect(self._run_search)

            self._search = QLineEdit()
            self._search.setPlaceholderText(self._page.search_placeholder)
            self._search.setClearButtonEnabled(True)
            self._search.setMinimumWidth(280)
            self._search.setMaximumWidth(420)
            self._search.textChanged.connect(lambda _: self._search_timer.start())
            toolbar.addWidget(self._search)

        for widget in leading:
            toolbar.addWidget(widget)

        toolbar.addStretch(1)

        # The filter first: it narrows what the rest of the row's controls
        # then act on, and it lands in the same place on every screen.
        if self._filter is not None:
            toolbar.addWidget(self._filter)

        for widget in extras:
            toolbar.addWidget(widget)

        toolbar.addWidget(refresh)
        return toolbar

    # ---------------- hooks ----------------

    def open_create_dialog(self) -> None:
        """Override in screens that declare a `create_label`."""

    def toolbar_leading(self) -> list[QWidget]:
        """Controls for the start of the toolbar, where the search box sits.

        For a screen whose list is about one chosen thing: the choice is
        read before the rows it produced, not hunted for at the far end of
        the row. `toolbar_extras` is the other end.
        """
        return []

    def filter_options(self) -> Sequence[FilterOption]:
        """This screen's Filter choices. Empty means no filter box.

        The "show everything" entry is added for you — these are the ways
        of narrowing, not the default.
        """
        return ()

    def summary(self) -> Sequence[tuple[str, str]]:
        """Figures describing the list, as (caption, value) pairs.

        Deliberately given no rows: these describe the whole filtered list
        — "sold this month" — and one page cannot be added up into an
        answer about the period it is a hundredth of. A screen with money
        in its strip reads it from the totals its page result carries; one
        with counts reads them from `result.total`.
        """
        return ()

    def toolbar_extras(self) -> list[QWidget]:
        """Extra widgets to place between Filter/Sort and Refresh."""
        return []

    def quick_add_fields(self) -> Sequence[QuickAddField]:
        """The inline "add another" row's fields. Empty means no strip."""
        return ()

    def build_quick_add(self) -> object | None:
        """The create command for what's typed in that row, or None to
        abort — having put the cursor where the user must fix it."""
        return None

    def build_footer(self) -> QWidget | None:
        """Anything else pinned below the table."""
        return None

    def create_table(self, columns: Sequence[Column]) -> TableWidget:
        """The table widget for this screen. Override for a grouped list."""
        return DataTable(columns, placeholder=self._page.empty_message)

    def open_secondary_dialog(self, index: int) -> None:
        """One of `secondary_create_labels` was clicked, given by position."""

    def row_actions(self) -> Sequence[RowAction]:
        """Buttons drawn inside every row. Empty means no actions column."""
        return ()

    def on_row_action(self, key: str, row: object) -> None:
        """Handle a click on one of `row_actions()`, for the row clicked."""

    def record_card(self, row: object) -> RecordCard | None:
        """This row written out in full, for `VIEW_ACTION`.

        Only screens that offer that action need answer. None means the
        record could not be written yet — a screen whose name lookups have
        not landed says so rather than showing a card full of dashes.
        """
        return None

    def on_rows_loaded(self, rows: list) -> None:
        """Extra handling after rows land — the base already renders them."""

    # ---------------- behaviour ----------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self.reload()

    def reload(self) -> None:
        """Fetch the page the screen is on again. The view model holds the
        search term, the filter and the order, so there is nothing to
        gather here."""
        self._view_model.reload()

    def reload_from_start(self) -> None:
        """For a change to *what* is listed — another period, another item,
        another party — rather than a refresh of it."""
        self._view_model.reload_from_start()

    def set_initial_sort(self, header: str, descending: bool = False) -> None:
        """Open the list in a particular order.

        Marks the heading and tells the view model in one call: doing only
        the first would draw a sorted column over rows the query never
        ordered. Asks for nothing — the screen has not made its first
        request yet.
        """
        self._table.sorting.sort_by(header, descending)
        self._view_model.open_sorted_by(self._table.sorting.sort_field, descending)

    def set_initial_filter(self, label: str) -> None:
        """Open the list already narrowed.

        Signals blocked, because a filter box set here would otherwise
        read as the user narrowing it — the screen would fetch every row
        and then immediately fetch the narrowed set over the top.
        """
        if self._filter is None:
            return
        self._filter.blockSignals(True)
        self._filter.select(label)
        self._filter.blockSignals(False)
        self._view_model.open_filtered_by(self._filter.current_value())

    def apply_search(self, term: str) -> None:
        """Entry point for the global header search box."""
        if self._search is None:
            return
        self._search.setText(term)
        self._run_search()

    def _run_search(self) -> None:
        if self._search is None:
            return
        self._view_model.set_search(self._search.text())

    def _on_filter_changed(self) -> None:
        if self._filter is not None:
            self._view_model.set_filter(self._filter.current_value())

    def _on_sort_changed(self) -> None:
        self._view_model.set_sort(
            self._table.sorting.sort_field, self._table.sorting.descending
        )

    @property
    def supports_search(self) -> bool:
        return self._search is not None

    def focus_search(self) -> bool:
        """Put the cursor in this screen's search box. False if it has none."""
        if self._search is None:
            return False
        self._search.setFocus()
        self._search.selectAll()
        return True

    @property
    def table(self) -> TableWidget:
        return self._table

    @property
    def view_model(self) -> CollectionViewModelBase:
        return self._view_model

    # ---------------- view model callbacks ----------------

    def _on_page_loaded(self, result: PageResult) -> None:
        self._loaded_once = True
        term = self._search.text().strip() if self._search is not None else ""
        self._table.set_placeholder(
            f'No matches for "{term}".' if term else self._page.empty_message
        )
        self._table.set_rows(result.rows)
        # The count is of the whole list; the bar says which of it these
        # rows are. Each number appears once.
        self._count_label.setText(self._page.count_label(result.total))
        self._pagination.set_page(result)
        self._summary.set_items(self.summary())
        self.on_rows_loaded(result.rows)

    def set_filter_options(self, filters: Sequence[FilterOption]) -> None:
        """Replace the Filter choices — for screens whose options are only
        knowable once their reference data has arrived."""
        if self._filter is not None:
            self._filter.set_options(filters)

    @property
    def filter_box(self) -> FilterBox | None:
        return self._filter

    def _on_busy_changed(self, busy: bool) -> None:
        # Only stand in for content the user has never seen. Saying
        # "Loading…" over an already-populated table on every refresh is
        # noise; on a first, still-empty load it's the difference between
        # "working" and "broken".
        if busy and not self._loaded_once:
            self._table.set_placeholder("Loading…")

    def _on_error(self, message: str) -> None:
        self._table.set_placeholder(self._page.empty_message)
        QMessageBox.warning(self, self._page.title, message)


class EditableCollectionView(CollectionView):
    """
    A list screen whose records can be corrected or removed in place.

    The two actions sit in the row, not in a toolbar above it. A toolbar
    button acts on "the selection" — the user has to make one first, and
    then trust that it is the row they meant. A button inside the row names
    its own target.

    Subclasses supply `open_edit_dialog`; deleting is the same everywhere,
    so it is handled here.
    """

    def row_actions(self) -> Sequence[RowAction]:
        if not self._view_model.supports_editing:
            return ()
        return (RowAction(_EDIT, "Edit"), RowAction(_REMOVE, "Remove", tone="danger"))

    # ---------------- hooks ----------------

    def open_edit_dialog(self, row: object) -> None:
        """Open this screen's form, filled in with `row`."""
        raise NotImplementedError

    def describe(self, row: object) -> str:
        """How a record names itself in the delete confirmation."""
        return str(getattr(row, "name", row))

    def delete_warning(self, row: object) -> str:
        """What else goes when this record does.

        Most screens take the record and nothing else. The two that also
        delete the documents behind it say so here, because a warning that
        doesn't name the blast radius isn't one.
        """
        return "This cannot be undone."

    # ---------------- behaviour ----------------

    def on_row_action(self, key: str, row: object) -> None:
        if key == _EDIT:
            self.open_edit_dialog(row)
        else:
            self._remove(row)

    def _remove(self, row: object) -> None:
        if not confirm_destructive(
            self,
            title=f"Delete {self._page.unit}",
            message=f"Delete {self.describe(row)}?\n\n{self.delete_warning(row)}",
            confirm_label=f"Delete {self._page.unit}",
        ):
            return
        self._view_model.delete(row.id)
