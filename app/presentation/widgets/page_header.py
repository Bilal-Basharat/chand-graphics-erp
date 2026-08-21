"""
The block every screen opens with: breadcrumb, title, and right-aligned
action buttons — and `panel_title`, the same idea one level down.

Exists so the vertical rhythm at the top of a screen is defined once —
when each view built this by hand the spacing drifted screen to screen.
"""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

_CRUMB_ROOT = "Home"


def panel_title(text: str) -> QLabel:
    """A panel's heading, inset from the panel's own edge.

    Panels carry no padding of their own — the tables inside them run edge
    to edge — so the heading brings its own, and brings the same on every
    panel that has nothing sitting beside it.
    """
    label = QLabel(text)
    label.setProperty("role", "panelTitle")
    label.setContentsMargins(18, 14, 18, 10)
    return label


class PageHeader(QWidget):
    def __init__(
        self,
        crumb_trail: tuple[str, ...],
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        crumb = QLabel(" / ".join((_CRUMB_ROOT, *crumb_trail)))
        crumb.setProperty("role", "crumb")
        outer.addWidget(crumb)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        title_label = QLabel(title)
        title_label.setProperty("role", "pageTitle")
        row.addWidget(title_label)
        row.addStretch(1)

        self._actions = QHBoxLayout()
        self._actions.setContentsMargins(0, 0, 0, 0)
        self._actions.setSpacing(8)
        row.addLayout(self._actions)

        outer.addLayout(row)

    def add_action(self, label: str, on_click, variant: str = "outline") -> QPushButton:
        """Add a right-aligned action button. Primary action goes last so it
        sits at the trailing edge, where the eye lands after reading the title."""
        button = QPushButton(label)
        button.setProperty("variant", variant)
        button.clicked.connect(on_click)
        self._actions.addWidget(button)
        return button

    def add_widget(self, widget: QWidget) -> QWidget:
        """Place an arbitrary control in the action area — a page-level
        filter, say, that isn't a button."""
        self._actions.addWidget(widget)
        return widget
