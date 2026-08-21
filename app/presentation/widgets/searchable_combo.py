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

It narrows two ways, and the difference matters at volume. Filled with a
list it holds, it filters that list here. Given a `searchRequested`
listener, it asks for matches instead — because a box that can only
filter what it was handed can only find what somebody decided to hand it,
and a shop with two thousand items will be handed a fraction.
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QComboBox, QCompleter, QWidget

SEARCH_DEBOUNCE_MS = 250
"""How long typing pauses before it becomes a question. Shared with the
list screens' search boxes so the two cannot drift apart."""


class SearchableComboBox(QComboBox):
    """Two of its parts are named for the stylesheet (see theme/stylesheet.py):
    `ComboSearchField`, the line edit inside the box, which has to be told
    not to draw a second box; and `ComboSearchPopup`, the list of matches,
    which is the completer's own top-level view rather than a child of the
    combo and so cannot be reached by the rule that styles a dropped-down
    list.
    """

    searchRequested = Signal(str)
    """What has been typed, once typing has paused. Connected only by the
    callers whose list is too long to hold; the rest filter locally."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._placeholder: tuple[str, Any] | None = None
        self.setEditable(True)
        # Typing names an item; it never adds one.
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lineEdit().setObjectName("ComboSearchField")
        self.lineEdit().editingFinished.connect(self._settle)
        # A line edit is left with its cursor at the end of any text it is
        # given, and scrolls there — so a name wider than the box reads
        # "…& Sons (Lahore)" when what tells one customer from another is
        # how the name begins. Both the ways a name arrives are caught:
        # written into the box, and picked from the list.
        self.lineEdit().textChanged.connect(self._on_text_set)
        self.currentIndexChanged.connect(self._on_choice_made)

        self._typing = QTimer(self)
        self._typing.setSingleShot(True)
        self._typing.setInterval(SEARCH_DEBOUNCE_MS)
        self._typing.timeout.connect(lambda: self.searchRequested.emit(self.currentText()))
        # `textEdited`, not `textChanged`: the latter also fires when this
        # widget sets its own text — settling it, or refilling it with
        # what came back — and the box would then ask about its own answer.
        self.lineEdit().textEdited.connect(lambda _text: self._typing.start())

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

    def set_placeholder_item(self, label: str, data: Any = None) -> None:
        """A first entry that is not one of the records — "Walk-in
        customer", "— choose a supplier —".

        Remembered rather than merely added, because every refill rebuilds
        the list: a search that dropped it would turn "no supplier chosen"
        into whichever supplier happened to match, and the form would
        accept it.
        """
        renaming = self._placeholder is not None and self.count() > 0
        self._placeholder = (label, data)
        if renaming:
            # It is always the first row — `set_options` re-adds it there
            # and `_offer` inserts after it — so saying so again renames
            # the row already standing rather than stacking a second
            # sentinel on top of it.
            with self.keeping_typed_text():
                self.setItemText(0, label)
                self.setItemData(0, data)
            return
        # Deliberately not followed by `setCurrentIndex(0)`: an empty box
        # takes the first row it is given as its choice anyway, and a box
        # that is not empty is already showing one — made by the person
        # using it, or from another screen — which a sentinel arriving
        # afterwards must not quietly take back.
        self.insertItem(0, label, data)

    def select(self, label: str, data: Any) -> None:
        """Make this record the choice, adding it if the list lacks it.

        The choice can be made somewhere other than this box — the Ledger
        button on a customer's row — and the box holds a page of names,
        not every name. Waiting for the record to turn up in that page
        would mean never opening the account of anyone outside it.
        """
        self.setCurrentIndex(self._offer(label, data))

    def _offer(self, label: str, data: Any) -> int:
        """Where `data` sits in the list, putting it there if it is absent.

        Directly after the placeholder, which stays the first row.
        """
        index = self.findData(data)
        if index < 0:
            index = 1 if self._placeholder is not None else 0
            self.insertItem(index, label, data)
        return index

    @contextmanager
    def keeping_typed_text(self) -> Iterator[None]:
        """Hold what is half-typed across a change to the list under it.

        An editable QComboBox re-reads its line edit from the row that is
        selected whenever anything about that row changes — the list being
        refilled, the selection moving, or merely data being put on the
        row. Qt offers no way to decline that and blocking the box's own
        signals does not stop it, because the box is the *receiver* of the
        model's.

        Public because a caller that decorates the rows needs it as much as
        the refill below does: the item picker writes each row's stock
        figure straight after a search, and the row it writes first is the
        selected one — which put the item's name where the word being
        searched for had been, and made the search look broken.

        Only while the box is being typed into. With the focus elsewhere
        there is nothing half-typed to protect, and the box should go on
        showing the choice that stands — a list arriving for a box nobody
        is holding must leave it reading as what it answers.
        """
        if not self.hasFocus():
            yield
            return
        typed, cursor = self.lineEdit().text(), self.lineEdit().cursorPosition()
        try:
            yield
        finally:
            if self.lineEdit().text() != typed:
                self.lineEdit().setText(typed)
                self.lineEdit().setCursorPosition(cursor)

    def set_options(
        self,
        rows: Sequence[tuple[str, Any]],
        *,
        term: str | None = None,
        keep_selected: bool = True,
    ) -> None:
        """Replace what can be chosen, without disturbing what was.

        `term` is what the caller asked about. A batch answering a term
        the box has since typed past is dropped: the text in the box is
        the question, so it is also the only staleness check needed.

        The record already chosen is kept even when it is not in the new
        batch — pick "Black Ink", type "paper", and the box must still
        answer Black Ink until something else is deliberately chosen.
        """
        if term is not None and term.strip() != self.currentText().strip():
            return

        chosen, chosen_label = self.currentData(), self.itemText(self.currentIndex())
        typed = self.lineEdit().text()

        with self.keeping_typed_text():
            self.blockSignals(True)
            self.clear()
            if self._placeholder is not None:
                self.addItem(*self._placeholder)
            for label, data in rows:
                self.addItem(label, data)

            # `_offer` puts the chosen record back when the new batch is
            # off the end of it, rather than letting a search silently
            # change what was chosen.
            index = (
                self._offer(chosen_label, chosen) if keep_selected and chosen is not None else -1
            )
            if index < 0:
                index = self.findText(typed.strip(), Qt.MatchFlag.MatchFixedString)
            self.setCurrentIndex(max(index, 0))
            self.blockSignals(False)

        if term is not None:
            self._show_matches()

    def _show_matches(self) -> None:
        """Put the list of matches back in front of whoever asked for it.

        The completer builds its list when a key is pressed. Matches
        fetched for that key arrive a moment later, so by the time they are
        here the list on screen is the one from before them — and the
        answer to what was typed would only appear on typing something
        else. Asking again with the same text redraws it against the rows
        that have since arrived.
        """
        completer = self.completer()
        if completer is None or not self.hasFocus():
            return
        completer.setCompletionPrefix(self.lineEdit().text())
        completer.complete()

    def focus_search(self) -> None:
        """Ready for the next search: what is in the box is selected, so
        typing replaces the last choice instead of being appended to it."""
        self.setFocus()
        self._select_all()

    def _on_text_set(self, _text: str) -> None:
        # Never while it is being typed into: the cursor is then somebody's
        # place in what they are writing, not a scroll position.
        if not self.hasFocus():
            self.lineEdit().setCursorPosition(0)

    def _on_choice_made(self) -> None:
        # Not while text is selected: arriving on the box selects what it
        # holds so that typing replaces it, and moving the cursor would
        # drop that selection — see `focusInEvent`.
        if not self.lineEdit().hasSelectedText():
            self.lineEdit().setCursorPosition(0)

    def _select_all(self) -> None:
        """Select what the box holds, with its start left on screen.

        Selected backwards, from the end to the beginning, so the cursor
        comes to rest at the start of the name and the box scrolls there.
        Selected the usual way round the cursor sits at the end, and a
        name wider than the box shows only how it finishes.

        Only while the box still holds the focus it was given a moment
        ago: something else may have taken it since, and selecting must
        never be a way of taking it back.
        """
        if not self.hasFocus():
            return
        length = len(self.lineEdit().text())
        self.lineEdit().setSelection(length, -length)

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
