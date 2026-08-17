"""
Where you are in a list, and how to get to the rest of it.

A shop's records outgrow one screenful, and until this existed the list
simply stopped — at five hundred rows, with nothing to say it had. So the
strip says two things at once: which rows these are ("Showing 101–200")
and, in the count beside the panel's title, how many there are altogether.
Between them there is no page the user cannot see they have not reached.

It hides itself when everything fits on one page. Twelve of these lists
are a dozen rows long and always will be; a dead row of greyed arrows
under each of them is chrome that never earns its space.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

from app.application.dto.queries import PageResult

PAGE_SIZES = (50, 100, 200, 500)
"""What a page may be set to. The last is `MAX_PAGE_SIZE`: past that a
page stops being a screenful to read and becomes a way of asking for the
table back."""


class PaginationBar(QWidget):
    pageRequested = Signal(int)
    pageSizeChanged = Signal(int)

    def __init__(self, page_size: int = 100, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = 1
        self._page_count = 1

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 8, 18, 10)
        row.setSpacing(8)

        self._range = QLabel("")
        self._range.setProperty("role", "panelSub")

        self._size = QComboBox()
        for size in PAGE_SIZES:
            self._size.addItem(f"{size} per page", size)
        self._size.setCurrentIndex(max(0, self._size.findData(page_size)))
        self._size.currentIndexChanged.connect(
            lambda _index: self.pageSizeChanged.emit(self._size.currentData())
        )

        # Ends and steps, in reading order. The words rather than arrows
        # alone on the two steps: they are the buttons that get used, and
        # "‹" on its own is a smaller target than the word beside it.
        self._first = _button("«", "First page", lambda: self.pageRequested.emit(1))
        self._previous = _button(
            "‹ Previous", "Previous page", lambda: self.pageRequested.emit(self._page - 1)
        )
        self._next = _button(
            "Next ›", "Next page", lambda: self.pageRequested.emit(self._page + 1)
        )
        self._last = _button(
            "»", "Last page", lambda: self.pageRequested.emit(self._page_count)
        )

        row.addWidget(self._range)
        row.addStretch(1)
        row.addWidget(self._size)
        row.addSpacing(4)
        for button in (self._first, self._previous, self._next, self._last):
            row.addWidget(button)

        self.hide()

    def set_page(self, result: PageResult) -> None:
        """Show where this page sits. The one way this widget is told
        anything, so its text and its buttons cannot disagree."""
        self._page = result.page
        self._page_count = result.page_count

        self._range.setText(
            f"Showing {result.first_index:,}–{result.last_index:,}" if result.rows else ""
        )

        size = self._size.findData(result.page_size)
        if size >= 0 and size != self._size.currentIndex():
            self._size.blockSignals(True)
            self._size.setCurrentIndex(size)
            self._size.blockSignals(False)

        for button in (self._first, self._previous):
            button.setEnabled(result.has_previous)
        for button in (self._next, self._last):
            button.setEnabled(result.has_next)

        self.setVisible(result.page_count > 1)


def _button(label: str, hint: str, on_click) -> QPushButton:
    button = QPushButton(label)
    button.setProperty("variant", "outline")
    button.setToolTip(hint)
    button.clicked.connect(on_click)
    return button
