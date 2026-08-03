"""
The shared anatomy of every list screen.

Each module screen is: header, then a panel holding a toolbar and a table.
Subclasses declare their copy and columns via `CollectionPage`, and
override the hooks below for whatever is genuinely theirs (the create
dialog, extra filters, a footer strip). Nothing about layout, spacing,
search debouncing, loading state or error routing is restated per screen.

Hooks, all optional:
    open_create_dialog()  - what the header's primary button does
    filter_options()      - the screen's Filter choices
    summary()             - the figures shown beside the panel title
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

from app.presentation.dialogs.confirm import confirm_destructive
from app.presentation.viewmodels.collection_viewmodel import CollectionViewModelBase
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.grouped_table import GroupedTable
from app.presentation.widgets.list_controls import FilterBox, FilterOption
from app.presentation.widgets.page_header import PageHeader
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


@dataclass(frozen=True, slots=True)
class CollectionPage:
    crumb: tuple[str, ...]
    title: str
    subtitle: str
    panel_title: str
    empty_message: str
    unit: str
    """Noun for the record count, e.g. "customer" -> "12 customers"."""
    unit_plural: str | None = None
    search_placeholder: str | None = None
    create_label: str | None = None
    quick_add_label: str | None = None
    """Wording on the inline row's button. Defaults to "Add"."""

    def count_label(self, count: int) -> str:
        if count == 1:
            return f"1 {self.unit}"
        plural = self.unit_plural or f"{self.unit}s"
        return f"{count} {plural}"


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
        # What the view model last returned, before the filter and the
        # column sort had their say. Kept so changing either re-renders
        # instead of re-querying for rows that are already here.
        self._rows: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(16)

        self._header = PageHeader(page.crumb, page.title, page.subtitle)
        if page.create_label:
            self._header.add_action(page.create_label, self.open_create_dialog, variant="primary")
        outer.addWidget(self._header)

        outer.addWidget(self._build_panel(columns), 1)

        view_model.rowsLoaded.connect(self._on_rows_loaded)
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
            self._filter.changed.connect(self._render_rows)

        extras = self.toolbar_extras()
        if self._page.search_placeholder or extras or self._filter is not None:
            layout.addLayout(self._build_toolbar(extras, refresh))
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
        # Sorting lives on the headings, so the table owns it and the
        # screen only has to re-render when it changes.
        table.sorting.changed.connect(self._render_rows)
        if delegate is not None:
            delegate.setParent(table)
            delegate.attach(table, column=len(columns) - 1)
            delegate.triggered.connect(self._on_row_action)
        return table

    def _on_row_action(self, key: str, row_index: int) -> None:
        row = self._table.row_at(row_index)
        if row is not None:
            self.on_row_action(key, row)

    def _build_toolbar(self, extras: list[QWidget], refresh: QPushButton) -> QHBoxLayout:
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

    def filter_options(self) -> Sequence[FilterOption]:
        """This screen's Filter choices. Empty means no filter box.

        The "show everything" entry is added for you — these are the ways
        of narrowing, not the default.
        """
        return ()

    def summary(self, rows: list) -> Sequence[tuple[str, str]]:
        """Figures describing the rows on screen, as (caption, value) pairs.

        Given the rows actually shown, not everything fetched, so the
        figures always add up to what the user is looking at.
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

    def row_actions(self) -> Sequence[RowAction]:
        """Buttons drawn inside every row. Empty means no actions column."""
        return ()

    def on_row_action(self, key: str, row: object) -> None:
        """Handle a click on one of `row_actions()`, for the row clicked."""

    def on_rows_loaded(self, rows: list) -> None:
        """Extra handling after rows land — the base already renders them."""

    # ---------------- behaviour ----------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self.reload()

    def reload(self) -> None:
        term = self._search.text() if self._search is not None else ""
        if term.strip():
            self._view_model.search(term)
        else:
            self._view_model.load()

    def apply_search(self, term: str) -> None:
        """Entry point for the global header search box."""
        if self._search is None:
            return
        self._search.setText(term)
        self._run_search()

    def _run_search(self) -> None:
        if self._search is None:
            return
        self._view_model.search(self._search.text())

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

    def _on_rows_loaded(self, rows: list) -> None:
        self._loaded_once = True
        self._rows = rows
        self._render_rows()

    def _render_rows(self) -> None:
        rows = self._rows if self._filter is None else self._filter.apply(self._rows)
        rows = self._table.sorting.sort(rows)
        term = self._search.text().strip() if self._search is not None else ""
        self._table.set_placeholder(
            f'No matches for "{term}".' if term else self._page.empty_message
        )
        self._table.set_rows(rows)
        self._count_label.setText(self._page.count_label(len(rows)))
        self._summary.set_items(self.summary(rows))
        self.on_rows_loaded(rows)

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
