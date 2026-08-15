"""
A dropdown you can type into.

A shop's catalogue outgrows a dropdown long before the shop outgrows
anything else: at a thousand items, finding the one being sold by
scrolling is the slowest part of writing an invoice. Making the box
editable turns that scroll into a filter — type any part of a name and
the list narrows to what matches it.

What it is not is a text field. The choice is still one of the rows: text
that names no item is put back to the item that is actually selected, so
`currentData()` always answers with something the caller can act on, and
the box never shows a choice that was never made.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QComboBox, QCompleter, QWidget


class SearchableComboBox(QComboBox):
    """Two of its parts are named for the stylesheet (see theme/stylesheet.py):
    `ComboSearchField`, the line edit inside the box, which has to be told
    not to draw a second box; and `ComboSearchPopup`, the list of matches,
    which is the completer's own top-level view rather than a child of the
    combo and so cannot be reached by the rule that styles a dropped-down
    list.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        # Typing names an item; it never adds one.
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lineEdit().setObjectName("ComboSearchField")
        self.lineEdit().editingFinished.connect(self._settle)

        completer = QCompleter(self.model(), self)
        # Contains rather than starts-with: "80 gsm art paper" is looked
        # for by "gsm", which is how a shopkeeper remembers what is on the
        # shelf. Case-insensitively, for the same reason.
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.popup().setObjectName("ComboSearchPopup")
        self.setCompleter(completer)

    def setItemDelegate(self, delegate) -> None:  # noqa: N802 (Qt override)
        """Draw both lists the same way.

        The matches are painted by the completer's own view, so a delegate
        set on the combo alone would draw a row one way when the list is
        dropped down and another way when it has been searched.
        """
        super().setItemDelegate(delegate)
        # Qt sets a delegate of its own from the base constructor, before
        # there is a completer to pass it on to.
        completer = self.completer()
        if completer is not None:
            completer.popup().setItemDelegate(delegate)

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (Qt override)
        """Arrive with what is already in the box selected.

        The box is never empty — it shows the choice standing — so without
        this, typing lands beside that name instead of starting a search:
        "Black Ink" typed at a box reading "80 gsm Art Paper" searches for
        "80 gsm Art PaperBlack Ink" and finds nothing.

        Queued, because a click sets the cursor *after* the focus it
        causes, and would undo a selection made now.
        """
        super().focusInEvent(event)
        QTimer.singleShot(0, self, self._select_all)

    def focus_search(self) -> None:
        """Ready for the next search: what is in the box is selected, so
        typing replaces the last choice instead of being appended to it."""
        self.setFocus()
        self.lineEdit().selectAll()

    def _select_all(self) -> None:
        # Only while the box still holds the focus it was given a moment
        # ago: something else may have taken it since, and selecting must
        # never be a way of taking it back.
        if self.hasFocus():
            self.lineEdit().selectAll()

    def _settle(self) -> None:
        """Leave the box showing a real choice, once typing has finished.

        Half-typed or unmatched text is not a selection, and leaving it on
        screen would claim one was made: the caller would go on to add the
        item that was selected before, under a name nobody chose.
        """
        index = self.findText(self.currentText(), Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.setEditText(self.itemText(self.currentIndex()))
