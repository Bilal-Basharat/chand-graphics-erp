"""
The one-line "add another" row pinned below a list.

Master data arrives in runs — a delivery of stock, the cabinets to file
it in, the categories a month's expenses fall under. Reopening a
modal for each one is the wrong shape for that work: the dialog is right
when a record needs thought, and in the way when it needs typing.

This owns the strip's chrome and its submit lifecycle. What each screen
supplies is its own fields and its own command, because that is the only
part that genuinely differs — see `CollectionView.quick_add_fields`.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QWidget,
)

from app.presentation.theme import tokens as t
from app.presentation.widgets.input_validation import MoneyInput, PhoneInput


@dataclass(frozen=True, slots=True)
class QuickAddField:
    widget: QWidget
    stretch: int = 1
    """Share of the strip's width, as in a box layout. Give the field
    people type most into the largest share."""


class QuickAddStrip(QFrame):
    """A row of fields and an Add button. Emits `submitted` on either."""

    submitted = Signal()

    def __init__(
        self,
        fields: Sequence[QuickAddField],
        button_label: str = "Add",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # objectName + a rule in stylesheet.py, not a local setStyleSheet()
        # call — a bare declaration block here would cascade into every
        # child input and strip their borders (see theme/stylesheet.py).
        self.setObjectName("AddRowStrip")
        self._fields = list(fields)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(8)

        plus = QLabel("+")
        plus.setStyleSheet(
            f"color: {t.PRIMARY}; font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 15px;"
        )
        layout.addWidget(plus)

        for field in self._fields:
            # Enter submits from any text field: the hands are already on
            # the keyboard, and reaching for the button breaks the run.
            if isinstance(field.widget, QLineEdit):
                field.widget.returnPressed.connect(self.submitted.emit)
            layout.addWidget(field.widget, field.stretch)

        button = QPushButton(button_label)
        button.setProperty("variant", "primary")
        button.clicked.connect(self.submitted.emit)
        layout.addWidget(button)

    # ---------------- behaviour ----------------

    def focus_first(self) -> None:
        """Put the cursor back at the start of the row, ready for the next."""
        if self._fields:
            self._fields[0].widget.setFocus()

    def reset(self) -> None:
        """Empty the row after a record is created.

        Combo boxes go back to their first entry rather than being
        cleared: that entry is the screen's "none chosen" prompt, and it
        is still the right starting point for the next record.
        """
        for field in self._fields:
            widget = field.widget
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QTextEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif hasattr(widget, "setValue"):
                widget.setValue(0)
        self.focus_first()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        # Double-clicking anywhere on the strip starts a new record, so the
        # whole band is a target rather than just the first field.
        super().mouseDoubleClickEvent(event)
        self.focus_first()


def line_edit(placeholder: str) -> QLineEdit:
    """A strip field, since every screen wants the same one."""
    field = QLineEdit()
    field.setPlaceholderText(placeholder)
    field.setClearButtonEnabled(True)
    return field


def money_edit(placeholder: str, *, signed: bool = False) -> MoneyInput:
    """A strip field for an amount: `line_edit`'s chrome, but it will only
    ever hold a number."""
    field = MoneyInput(signed=signed, placeholder=placeholder)
    field.setClearButtonEnabled(True)
    return field


def phone_edit(placeholder: str) -> PhoneInput:
    """A strip field for a phone number, chrome to match the rest."""
    field = PhoneInput(placeholder=placeholder)
    field.setClearButtonEnabled(True)
    return field


def combo(prompt: str) -> QComboBox:
    """A strip dropdown whose first entry is the "none chosen" prompt."""
    box = QComboBox()
    box.addItem(prompt, None)
    return box


def refill(box: QComboBox, prompt: str, entries: Sequence[tuple[str, int]]) -> None:
    """Replace a strip dropdown's options, keeping the current choice.

    The options come from another screen's records — cabinets, expense
    categories — so they change under this one mid-session. Rebuilding
    without this would silently drop what the user had chosen.
    """
    previous = box.currentData()
    box.clear()
    box.addItem(prompt, None)
    for label, value in entries:
        box.addItem(label, value)
    index = box.findData(previous)
    box.setCurrentIndex(max(index, 0))
