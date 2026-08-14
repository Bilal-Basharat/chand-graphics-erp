"""
Left navigation rail. Purely presentational: renders the fixed nav
structure and emits `navigationRequested(Route)` on click. Knows nothing
about which routes have a real screen behind them yet — that's MainWindow's
concern.

The rail collapses to an icon-only strip, and slides between the two
widths rather than snapping: the jump was the whole window's layout
changing in one frame, which reads as a glitch. Collapsed, each row keeps
its icon and gains a tooltip carrying the label it can no longer show, so
the navigation stays usable rather than becoming a column of guesses.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QEnterEvent, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.presentation.navigation.routes import Route
from app.presentation.theme import tokens as t
from app.presentation.widgets.nav_icons import ICON_SIZE, nav_icon


@dataclass(frozen=True, slots=True)
class NavItem:
    """One row in the rail.

    A row with children is a folder: it has no screen of its own and opens
    the rows underneath it instead. Three payment screens listed flat
    among the documents they belong to made the Operations group read as
    six unrelated destinations; folded away they read as one, which is
    what they are.
    """

    label: str
    route: Route | None = None
    icon: str = ""
    """Which drawing in `nav_icons` this row shows. Defaults to the
    route's own — a folder has no route, so it names one."""
    children: tuple["NavItem", ...] = ()

    @property
    def icon_name(self) -> str:
        return self.icon or (self.route.value if self.route is not None else "")


# Icons are keyed by route value and painted in nav_icons.py — see that
# module for why they aren't Unicode glyphs.
_NAV_GROUPS: list[tuple[str, tuple[NavItem, ...]]] = [
    ("Overview", (
        NavItem("Dashboard", Route.DASHBOARD),
    )),
    ("Operations", (
        NavItem("Sales", Route.SALES),
        NavItem("Purchases", Route.PURCHASES),
        NavItem("Payments", icon="payments", children=(
            NavItem("Sale payments", Route.SALE_PAYMENTS),
            NavItem("Purchase payments", Route.PURCHASE_PAYMENTS),
        )),
        NavItem("Payment methods", Route.PAYMENT_METHODS),
    )),
    ("Items", (
        NavItem("Inventory", Route.INVENTORY),
        NavItem("Cabinets", Route.CABINETS),
        NavItem("Inventory movement", Route.INVENTORY_MOVEMENT),
    )),
    ("Parties", (
        NavItem("Customers", Route.CUSTOMERS),
        NavItem("Suppliers", Route.SUPPLIERS),
        NavItem("Ledger", icon="ledger", children=(
            NavItem("Customer ledger", Route.CUSTOMER_LEDGER),
            NavItem("Supplier ledger", Route.SUPPLIER_LEDGER),
        )),
    )),
    ("Finance", (
        NavItem("Expenses", Route.EXPENSES),
        NavItem("Expense categories", Route.EXPENSE_CATEGORIES),
        NavItem("Reports", icon="reports", children=(
            NavItem("Profit & loss", Route.PROFIT_AND_LOSS),
            NavItem("Item profitability", Route.ITEM_PROFITABILITY),
            NavItem("Receivables ageing", Route.RECEIVABLES_AGEING),
            NavItem("Payables ageing", Route.PAYABLES_AGEING),
        )),
    )),
    ("System", (
        NavItem("Company settings", Route.COMPANY_SETTINGS),
        NavItem("Licence", Route.LICENSE),
        NavItem("My profile", Route.PROFILE),
    )),
]

# What stays reachable when the licence no longer opens the app: the
# screen a new key is entered on, and the user's own account.
UNLOCKED_ROUTES = frozenset({Route.LICENSE, Route.PROFILE})

COLLAPSED_WIDTH = 64
SIDEBAR_WIDTH = t.SIDEBAR_WIDTH
"""Re-exported so callers can talk about the rail's two widths together."""
_SLIDE_MS = 190

_OPEN = "⌄"
_CLOSED = "›"
"""Which way a folder's rows are. Glyphs rather than a painted icon
because the button's one icon slot already holds the row's subject, and
these are the same carets the header's account chip uses."""


class _NavButton(QPushButton):
    """
    A nav row whose icon follows its text colour.

    QSS drives the text colour per state, but an icon is a pixmap — it
    can't inherit that, so a grey icon would be left sitting on the blue
    active/hover background. The pixmap is re-tinted on each state change
    instead.

    A row nested under a folder keeps its icon but is indented past the
    rail's icon column, so the group reads as one block hanging off the
    row above it. The indent comes from QSS, keyed on the `depth`
    property; an empty icon name draws no icon at all.
    """

    def __init__(
        self,
        icon: str,
        label: str,
        *,
        depth: int = 0,
        checkable: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon = icon
        self._label = label
        self._depth = depth
        self._suffix = ""
        self._hovered = False
        self._collapsed = False
        self.setProperty("role", "navItem")
        self.setProperty("depth", depth)
        self.setCheckable(checkable)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        # A floor, so a cramped layout scrolls rather than slicing rows in
        # half. The rail scrolls now, but the guarantee belongs on the row.
        self.setMinimumHeight(34)
        self.set_collapsed(False)

    def set_suffix(self, suffix: str) -> None:
        """A marker after the label — the open/closed caret on a folder."""
        self._suffix = suffix
        self.set_collapsed(self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        # The tooltip only carries the label when the label isn't visible;
        # a tooltip repeating text already on screen is just noise.
        # Doubled: a button reads a lone "&" as the mnemonic marker, so
        # "Profit & loss" would appear as "Profit _loss" with the L
        # underlined. Nothing here wants keyboard accelerators.
        label = self._label.replace("&", "&&")
        text = f"   {label}{f'   {self._suffix}' if self._suffix else ''}"
        self.setText("" if collapsed else text)
        self.setToolTip(self._label if collapsed else "")
        self.setProperty("collapsed", collapsed)
        _repolish(self)

    def refresh_icon(self) -> None:
        if not self._icon:
            self.setIcon(QIcon())
            return
        highlighted = self.isChecked() or self._hovered
        self.setIcon(nav_icon(self._icon, "#ffffff" if highlighted else t.NAV_IDLE))

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802 (Qt override)
        super().enterEvent(event)
        self._hovered = True
        self.refresh_icon()

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().leaveEvent(event)
        self._hovered = False
        self.refresh_icon()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt override)
        super().setChecked(checked)
        self.refresh_icon()

    def nextCheckState(self) -> None:  # noqa: N802 (Qt override)
        super().nextCheckState()
        self.refresh_icon()


def _repolish(widget: QWidget) -> None:
    """Re-evaluate QSS after a dynamic property changes.

    Qt resolves property selectors when a widget is polished, not when the
    property is set, so without this a `[collapsed="true"]` rule would
    never take effect.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)


@dataclass(slots=True)
class _Folder:
    """A parent row and the rows it opens."""

    button: _NavButton
    rows: list[_NavButton] = field(default_factory=list)
    routes: frozenset[Route] = frozenset()
    is_open: bool = False


class Sidebar(QWidget):
    navigationRequested = Signal(Route)
    collapsedChanged = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        # A plain QWidget does not paint a stylesheet background on its own
        # — it needs this attribute, and without it the rail rendered as a
        # hole in the page with its rows floating on the canvas colour.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(t.SIDEBAR_WIDTH)

        self._buttons: dict[Route, _NavButton] = {}
        self._folders: list[_Folder] = []
        self._group_headings: list[QLabel] = []
        self._collapsed = False
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        # Both bounds are animated together: a fixed-width widget has its
        # minimum and maximum pinned to the same number, so moving only one
        # of them would leave the other holding the rail at its old size.
        self._slide = QPropertyAnimation(self, b"maximumWidth", self)
        self._slide.setDuration(_SLIDE_MS)
        self._slide.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._slide.valueChanged.connect(lambda width: self.setMinimumWidth(width))
        # Re-applied at the end as well as the start: the toggle's contents
        # are laid out for the width it had when they were set, and setting
        # the expanded label while the rail was still 64px wide left no room
        # for the icon, which then stayed missing.
        self._slide.finished.connect(self._sync_toggle)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # The rows scroll; the toggle does not. Laid out as one column the
        # rail demanded more height than a short screen has, and the rows
        # that didn't fit were cut through the middle rather than simply
        # being out of view.
        scroll = QScrollArea(self)
        scroll.setObjectName("SidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # With horizontal scrolling off, a scroll area adopts its content's
        # minimum width as its own — which would hold the collapsed rail a
        # couple of pixels wider than the icon strip it is meant to be.
        scroll.setMinimumWidth(0)

        rows = QWidget()
        rows.setObjectName("SidebarRows")
        rows_layout = QVBoxLayout(rows)
        rows_layout.setContentsMargins(0, 14, 0, 8)
        rows_layout.setSpacing(0)
        rows_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        for group_label, items in _NAV_GROUPS:
            rows_layout.addLayout(self._build_group(group_label, items))
        rows_layout.addStretch(1)

        scroll.setWidget(rows)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._build_toggle())

    def _build_group(self, label: str, items: tuple[NavItem, ...]) -> QVBoxLayout:
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(12, 0, 12, 12)
        group_layout.setSpacing(1)

        heading = QLabel(label.upper())
        heading.setProperty("role", "navLabel")
        heading.setContentsMargins(10, 4, 10, 6)
        self._group_headings.append(heading)
        group_layout.addWidget(heading)

        for item in items:
            if not item.children:
                group_layout.addWidget(self._build_row(item))
                continue
            # Built before the folder so it can hold them, added after so
            # they still land underneath it in the column.
            rows = [self._build_row(child, depth=1) for child in item.children]
            group_layout.addWidget(self._build_folder(item, rows))
            for row in rows:
                group_layout.addWidget(row)
                row.setVisible(False)  # after the add, so the layout can't re-show it

        return group_layout

    def _build_row(self, item: NavItem, depth: int = 0) -> _NavButton:
        button = _NavButton(item.icon_name, item.label, depth=depth)
        button.clicked.connect(
            lambda _checked, r=item.route: self.navigationRequested.emit(r)
        )
        self._button_group.addButton(button)
        self._buttons[item.route] = button
        return button

    def _build_folder(self, item: NavItem, rows: list[_NavButton]) -> _NavButton:
        # Not checkable, and out of the exclusive group: a folder is not
        # somewhere you can be, so it must never take the blue that marks
        # the screen you are on.
        button = _NavButton(item.icon_name, item.label, checkable=False)
        folder = _Folder(
            button=button,
            rows=rows,
            routes=frozenset(child.route for child in item.children if child.route),
        )
        self._folders.append(folder)
        button.clicked.connect(lambda _checked=False, f=folder: self._toggle_folder(f))
        self._sync_folder(folder)
        return button

    # ---------------- folders ----------------

    def _toggle_folder(self, folder: _Folder) -> None:
        # An icon-only rail has nowhere to put an indented list, so the
        # click that would have opened one opens the rail first.
        if self._collapsed:
            self.set_collapsed(False)
            self._set_folder_open(folder, True)
            return
        self._set_folder_open(folder, not folder.is_open)

    def _set_folder_open(self, folder: _Folder, is_open: bool) -> None:
        folder.is_open = is_open
        self._sync_folder(folder)

    def _sync_folder(self, folder: _Folder) -> None:
        visible = folder.is_open and not self._collapsed
        for row in folder.rows:
            row.setVisible(visible)
        folder.button.set_suffix(_OPEN if folder.is_open else _CLOSED)
        folder.button.refresh_icon()

    def _rows(self):
        """Every nav row in the rail, folders included."""
        return [*self._buttons.values(), *(folder.button for folder in self._folders)]

    def _build_toggle(self) -> QPushButton:
        self._toggle = QPushButton()
        self._toggle.setProperty("role", "sidebarFoot")
        self._toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._toggle.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._toggle.clicked.connect(self.toggle_collapsed)
        self._sync_toggle()
        return self._toggle

    # ---------------- collapsing ----------------

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed

        for button in self._rows():
            button.set_collapsed(collapsed)
        # Collapsing folds every folder away with the labels; expanding
        # leaves them folded rather than restoring what was open before,
        # so the rail comes back the same way every time.
        for folder in self._folders:
            folder.is_open = False
            self._sync_folder(folder)
        for heading in self._group_headings:
            # Group headings are words; there is nowhere to put them in an
            # icon-only rail, and abbreviating them would only puzzle.
            heading.setVisible(not collapsed)

        self._slide.stop()
        self._slide.setStartValue(self.width())
        self._slide.setEndValue(COLLAPSED_WIDTH if collapsed else t.SIDEBAR_WIDTH)
        self._slide.start()

        self._sync_toggle()
        # Emitted at once rather than when the slide ends: the header's
        # brand block lines up with the rail, and letting it jump into
        # place afterwards would undo the point of animating at all.
        self.collapsedChanged.emit(collapsed)

    def _sync_toggle(self) -> None:
        # A chevron pointing the way the rail will move, painted like every
        # other icon here rather than typed as « » — those arrive from
        # whichever font covers them and never match the rest.
        expand = self._collapsed
        self._toggle.setIcon(
            nav_icon("chevron_right" if expand else "chevron_left", t.NAV_IDLE)
        )
        self._toggle.setText("" if expand else "   Collapse menu")
        self._toggle.setToolTip("Expand menu" if expand else "")
        self._toggle.setProperty("collapsed", self._collapsed)
        _repolish(self._toggle)

    # ---------------- locking ----------------

    def set_locked(self, locked: bool) -> None:
        """Grey every destination a licence is required for.

        The rail is where navigation is offered, so this is where it stops
        being offered. It is not the enforcement — a screen can also be
        reached from the header search — but a row that still looked live
        and did nothing would read as a broken app rather than a licence
        that has run out.
        """
        for route, button in self._buttons.items():
            button.setEnabled(not locked or route in UNLOCKED_ROUTES)
        for folder in self._folders:
            folder.button.setEnabled(not locked)

    # ---------------- selection ----------------

    def set_active(self, route: Route) -> None:
        # A screen can be opened from somewhere other than the rail — the
        # dashboard's activity feed, the header search — so the folder it
        # lives in opens to show where the user has landed.
        for folder in self._folders:
            if route in folder.routes and not folder.is_open:
                self._set_folder_open(folder, True)

        button = self._buttons.get(route)
        if button is not None:
            button.setChecked(True)
        # The group deselects the previous button without routing through
        # setChecked(), so its icon has to be refreshed explicitly.
        for nav_button in self._rows():
            nav_button.refresh_icon()
