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

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QEnterEvent
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

# Icons are keyed by route value and painted in nav_icons.py — see that
# module for why they aren't Unicode glyphs.
#
# (group label, [(route, label)])
_NAV_GROUPS: list[tuple[str, list[tuple[Route, str]]]] = [
    ("Overview", [
        (Route.DASHBOARD, "Dashboard"),
    ]),
    ("Operations", [
        (Route.SALES, "Sales"),
        (Route.SALE_PAYMENTS, "Sale payments"),
        (Route.PURCHASES, "Purchases"),
        (Route.PURCHASE_PAYMENTS, "Purchase payments"),
        (Route.PAYMENT_METHODS, "Payment methods"),
    ]),
    ("Items", [
        (Route.WEDDING_CARDS, "Wedding cards"),
        (Route.INVENTORY_ITEMS, "Inventory items"),
        (Route.CABINETS, "Cabinets"),
        (Route.INVENTORY_MOVEMENT, "Inventory movement"),
    ]),
    ("Parties", [
        (Route.CUSTOMERS, "Customers"),
        (Route.SUPPLIERS, "Suppliers"),
    ]),
    ("Finance", [
        (Route.EXPENSES, "Expenses"),
        (Route.EXPENSE_CATEGORIES, "Expense categories"),
        (Route.REPORTS, "Reports"),
    ]),
    ("System", [
        (Route.COMPANY_SETTINGS, "Company settings"),
        (Route.PROFILE, "My profile"),
    ]),
]

COLLAPSED_WIDTH = 64
SIDEBAR_WIDTH = t.SIDEBAR_WIDTH
"""Re-exported so callers can talk about the rail's two widths together."""
_SLIDE_MS = 190


class _NavButton(QPushButton):
    """
    A nav row whose icon follows its text colour.

    QSS drives the text colour per state, but an icon is a pixmap — it
    can't inherit that, so a grey icon would be left sitting on the blue
    active/hover background. The pixmap is re-tinted on each state change
    instead.
    """

    def __init__(self, route: Route, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._route = route
        self._label = label
        self._hovered = False
        self._collapsed = False
        self.setProperty("role", "navItem")
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        # A floor, so a cramped layout scrolls rather than slicing rows in
        # half. The rail scrolls now, but the guarantee belongs on the row.
        self.setMinimumHeight(34)
        self.set_collapsed(False)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        # The tooltip only carries the label when the label isn't visible;
        # a tooltip repeating text already on screen is just noise.
        self.setText("" if collapsed else f"   {self._label}")
        self.setToolTip(self._label if collapsed else "")
        self.setProperty("collapsed", collapsed)
        _repolish(self)

    def refresh_icon(self) -> None:
        highlighted = self.isChecked() or self._hovered
        self.setIcon(nav_icon(self._route.value, "#ffffff" if highlighted else t.NAV_IDLE))

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

    def _build_group(self, label: str, items: list[tuple[Route, str]]) -> QVBoxLayout:
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(12, 0, 12, 12)
        group_layout.setSpacing(1)

        heading = QLabel(label.upper())
        heading.setProperty("role", "navLabel")
        heading.setContentsMargins(10, 4, 10, 6)
        self._group_headings.append(heading)
        group_layout.addWidget(heading)

        for route, text in items:
            button = _NavButton(route, text)
            button.clicked.connect(lambda _checked, r=route: self.navigationRequested.emit(r))
            self._button_group.addButton(button)
            self._buttons[route] = button
            group_layout.addWidget(button)

        return group_layout

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

        for button in self._buttons.values():
            button.set_collapsed(collapsed)
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

    # ---------------- selection ----------------

    def set_active(self, route: Route) -> None:
        button = self._buttons.get(route)
        if button is not None:
            button.setChecked(True)
        # The group deselects the previous button without routing through
        # setChecked(), so its icon has to be refreshed explicitly.
        for nav_button in self._buttons.values():
            nav_button.refresh_icon()
