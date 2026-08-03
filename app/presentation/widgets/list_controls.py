"""
The "show me only these" control every list screen offers.

Filtering runs over the rows already on screen rather than going back to
the database. These lists are bounded by design — a period of documents,
a shop's catalogue — so the whole set is in hand already, and re-querying
to narrow it would cost a round trip to answer a question the screen can
answer instantly.

Ordering is not here: that belongs to the column headings, where the
column you are already looking at is the thing you click (see
sortable_header.py).

Each screen declares its own choices as data. What a filter *means* is
the screen's business; presenting it, remembering which is chosen, and
applying it is this widget's.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QWidget

UNFILTERED = "Filter by"
"""What the control reads when nothing is being hidden. Written as the
prompt it is rather than as "All sales", so the box says what it does
before it has been touched."""


@dataclass(frozen=True, slots=True)
class FilterOption:
    label: str
    keep: Callable[[Any], bool] | None = None
    """`None` keeps everything — the entry the control opens on."""


class FilterBox(QComboBox):
    """One combo, its choices, and the rows they leave behind."""

    changed = Signal()

    def __init__(
        self, options: Sequence[FilterOption] = (), parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._options: list[FilterOption] = []
        self.setMinimumWidth(170)
        self.currentIndexChanged.connect(lambda _index: self.changed.emit())
        self.set_options(options)

    def set_options(self, options: Sequence[FilterOption]) -> None:
        """Replace the choices, keeping the current one if it survives.

        Some filters are only knowable once data has arrived — the expense
        categories, say. Rebuilding silently would drop the user's choice
        every time the screen refreshed, so it is restored by label.
        """
        chosen = self.currentText() if self._options else ""
        self._options = [FilterOption(UNFILTERED), *options]

        self.blockSignals(True)
        self.clear()
        for option in self._options:
            self.addItem(option.label)
        index = self.findText(chosen)
        self.setCurrentIndex(max(index, 0))
        self.blockSignals(False)

    def select(self, label: str) -> None:
        """Open the screen on a particular filter rather than on all rows."""
        index = self.findText(label)
        if index >= 0:
            self.setCurrentIndex(index)

    def apply(self, rows: list) -> list:
        index = self.currentIndex()
        if not 0 <= index < len(self._options):
            return rows
        keep = self._options[index].keep
        return rows if keep is None else [row for row in rows if keep(row)]
