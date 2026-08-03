"""
The dashboard's recent-activity feed.

Each entry is two lines — what happened, and who and how much — so it is
built from rows rather than dropped into a table: a table would need a
column for each and would read as data to compare, when this is a
narrative to skim.

The rows are selectable because they are things you look *at*, not just
past: picking one holds your place while you read the rest, which is what
a long feed needs and what a static column of text cannot give.
"""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.presentation.formatting import DASH
from app.presentation.widgets.qss import repolish


class _ActivityRow(QFrame):
    clicked = Signal(object)  # the row's record

    def __init__(self, record, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._record = record
        self.setProperty("role", "activityRow")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 9, 18, 9)
        layout.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(1)
        title = QLabel(record.title)
        title.setProperty("role", "activityTitle")
        meta = QLabel(record.meta)
        meta.setProperty("role", "activityMeta")
        text.addWidget(title)
        text.addWidget(meta)
        layout.addLayout(text)
        layout.addStretch(1)

        when = QLabel(record.when.strftime("%d %b, %H:%M") if record.when else DASH)
        when.setProperty("role", "activityWhen")
        layout.addWidget(when, alignment=Qt.AlignmentFlag.AlignTop)

    @property
    def record(self):
        return self._record

    def set_selected(self, selected: bool) -> None:
        if self.property("selected") == selected:
            return
        self.setProperty("selected", selected)
        # The selected rule recolours the labels inside the row, and
        # polishing a parent does not reach its children — see qss.repolish.
        repolish(self, children=True)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        super().mousePressEvent(event)
        self.clicked.emit(self._record)


class ActivityList(QScrollArea):
    """A scrolling feed of activity rows, one of which may be selected."""

    selected = Signal(object)  # the chosen record

    def __init__(self, empty_message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActivityScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._empty_message = empty_message
        self._rows: list[_ActivityRow] = []

        body = QWidget()
        body.setObjectName("ActivityBody")
        self._layout = QVBoxLayout(body)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setWidget(body)

    def set_records(self, records: Sequence) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []

        if not records:
            empty = QLabel(self._empty_message)
            empty.setProperty("role", "activityMeta")
            empty.setContentsMargins(18, 12, 18, 12)
            self._layout.addWidget(empty)
            self._layout.addStretch(1)
            return

        for record in records:
            row = _ActivityRow(record)
            row.clicked.connect(self._on_clicked)
            self._rows.append(row)
            self._layout.addWidget(row)
        # Keeps a short feed's rows at their natural height instead of
        # sharing the panel's spare space between them.
        self._layout.addStretch(1)

    def _on_clicked(self, record) -> None:
        for row in self._rows:
            row.set_selected(row.record is record)
        self.selected.emit(record)
