"""
The answer a list gives about itself: how much was sold, how much is
still unpaid.

Each figure sits in its own box with its caption, so a number is never
read without knowing what it counts and two figures can never be mistaken
for one. Run together as a sentence in the toolbar — which is where this
started — they read as a single ambiguous total beside unrelated controls.
"""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.presentation.theme import tokens as t


class SummaryStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def set_items(self, items: Sequence[tuple[str, str]]) -> None:
        while self._layout.count():
            entry = self._layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()

        for caption, value in items:
            self._layout.addWidget(_figure(caption, value))
        self.setVisible(bool(items))


def _figure(caption: str, value: str) -> QWidget:
    # Caption and figure on one line: stacked, each box grew taller than
    # the row it sits in and narrower than the number it holds. Side by
    # side they read as the phrase they are — "Unpaid 850.00".
    #
    # objectName + a rule in stylesheet.py rather than a local
    # setStyleSheet() call: a bare declaration block here would cascade
    # into the labels below and undo their own styling.
    block = QWidget()
    block.setObjectName("SummaryFigure")
    layout = QHBoxLayout(block)
    layout.setContentsMargins(14, 5, 14, 5)
    layout.setSpacing(9)

    label = QLabel(caption)
    label.setProperty("role", "statLabel")

    figure = QLabel(value)
    figure.setStyleSheet(
        f"color: {t.INK}; font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 14px;"
    )

    layout.addWidget(label)
    layout.addWidget(figure)
    return block
