"""
A record card on screen: the whole of one document in a window.

Every list in the app answers "which one" — this answers "what is on it".
It is read, never edited, so there is no Save: the two buttons at the foot
take the same card to paper, through `records/paper.py`.

One dialog for every kind of record, driven entirely by the `RecordCard`
it is given. A sale, a purchase, a job order, an expense and a period
report differ in which facts and which tables they carry, and this renders
whatever it is handed — so a new kind of record is a new builder, not a
new window.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.presentation.records import paper
from app.presentation.records.card import (
    TONE_COLORS,
    Field,
    RecordCard,
    Section,
    Total,
)
from app.presentation.theme import tokens as t
from app.presentation.widgets.data_table import DataTable
from app.presentation.widgets.page_scroll import page_scroller
from app.presentation.widgets.table_model import Column

_FIELD_COLUMNS = 4
"""Facts across the head of the card. Four keeps a customer's name on one
line at this width; a fifth would start eliding them."""

_WIDTH = 960
_MIN_HEIGHT = 300
_SCREEN_MARGIN = 90
"""Room left for the title bar and a little air, so a tall record opens
against the screen it is on rather than a number guessed here — 720 fits
a shop-counter laptop and wastes half a desktop monitor."""

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _available_height() -> int:
    screen = QApplication.primaryScreen()
    if screen is None:  # pragma: no cover - only without a display
        return 720
    return max(_MIN_HEIGHT, screen.availableGeometry().height() - _SCREEN_MARGIN)


class RecordCardDialog(QDialog):
    def __init__(self, card: RecordCard, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._card = card

        self.setWindowTitle(card.title)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = self._build_head()
        outer.addWidget(head)

        scroll, page = page_scroller()
        body = QVBoxLayout(page)
        body.setContentsMargins(22, 18, 22, 18)
        body.setSpacing(18)
        if card.fields:
            body.addWidget(self._build_fields(card.fields))
        for section in card.sections:
            body.addWidget(self._build_section(section))
        if card.totals:
            body.addLayout(self._build_totals(card.totals))
        if card.note:
            body.addWidget(self._build_note(card.note))
        body.addStretch(1)
        # The head and the buttons stay put; only the record between them
        # moves, so a long invoice never scrolls its own Print button away.
        outer.addWidget(scroll, 1)

        foot = self._build_actions()
        outer.addWidget(foot)

        # Wide enough for the six-column job item table to keep its
        # material list readable, and only as tall as the record needs —
        # an expense is four lines, and opening it in an invoice-sized
        # window puts most of the screen's attention on empty space.
        #
        # Polished first: the labels take their size from the stylesheet,
        # and an unpolished widget reports the height of the default font
        # instead — which measured the card a dozen pixels short and cut
        # the last line of the totals in half.
        for band in (head, page, foot):
            band.ensurePolished()
        wanted = head.sizeHint().height() + page.sizeHint().height() + foot.sizeHint().height()
        self.resize(_WIDTH, max(_MIN_HEIGHT, min(_available_height(), wanted)))

    # ---------------- construction ----------------

    def _build_head(self) -> QFrame:
        band = QFrame()
        band.setProperty("role", "cardBand")
        row = QHBoxLayout(band)
        row.setContentsMargins(22, 16, 22, 16)
        row.setSpacing(16)

        text = QVBoxLayout()
        text.setSpacing(2)
        kind = QLabel(self._card.kind.upper())
        kind.setProperty("role", "statLabel")
        reference = QLabel(self._card.reference)
        reference.setProperty("role", "pageTitle")
        text.addWidget(kind)
        text.addWidget(reference)
        if self._card.subtitle:
            subtitle = QLabel(self._card.subtitle)
            subtitle.setProperty("role", "panelSub")
            text.addWidget(subtitle)
        row.addLayout(text, 1)

        if self._card.status:
            status = QLabel(self._card.status)
            status.setProperty("role", "tag")
            status.setProperty("tone", _TAG_TONES[self._card.status_tone])
            row.addWidget(status, alignment=Qt.AlignmentFlag.AlignTop)
        return band

    def _build_fields(self, fields: tuple[Field, ...]) -> QWidget:
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(12)

        for index, field in enumerate(fields):
            block = QVBoxLayout()
            block.setSpacing(1)
            label = QLabel(field.label.upper())
            label.setProperty("role", "statLabel")
            value = QLabel(field.value)
            value.setStyleSheet(
                f"color: {TONE_COLORS[field.tone]}; font-size: 13.5px;"
                f" font-weight: {t.WEIGHT_MEDIUM};"
            )
            value.setWordWrap(True)
            block.addWidget(label)
            block.addWidget(value)
            grid.addLayout(block, index // _FIELD_COLUMNS, index % _FIELD_COLUMNS)

        for column in range(_FIELD_COLUMNS):
            grid.setColumnStretch(column, 1)
        return holder

    def _build_section(self, section: Section) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(1, 0, 1, 1)
        layout.setSpacing(0)

        title = QLabel(section.title)
        title.setProperty("role", "panelTitle")
        title.setContentsMargins(17, 12, 17, 10)
        layout.addWidget(title)

        # The app's table, so a line reads here exactly as it does in the
        # list behind this dialog. Rows are plain tuples, so each column
        # reads its own position out of one.
        table = DataTable(
            [
                Column(
                    heading.title,
                    lambda row, index=index: row[index],
                    align=heading.align,
                    width=heading.width,
                )
                for index, heading in enumerate(section.headings)
            ],
            placeholder=section.empty,
            sortable=False,
        )
        table.set_rows(list(section.rows))
        # The card scrolls as one page, so each table stands at its own
        # height instead of putting a scrollbar inside a scrollbar.
        table.fit_to_rows(minimum=1)
        layout.addWidget(table)
        return panel

    def _build_totals(self, totals: tuple[Total, ...]) -> QHBoxLayout:
        row = QHBoxLayout()
        # Against the right edge, under the amount columns of the table
        # above — where the eye already is, and where every printed
        # invoice puts them.
        row.addStretch(1)

        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(5)
        for index, total in enumerate(totals):
            size = 19 if total.strong else 13.5
            weight = t.WEIGHT_SEMIBOLD if total.strong else t.WEIGHT_MEDIUM
            label = QLabel(total.label)
            label.setStyleSheet(f"color: {t.MUTED}; font-size: {size * 0.72:.0f}px;")
            label.setAlignment(_RIGHT)
            value = QLabel(total.value)
            value.setStyleSheet(
                f"color: {TONE_COLORS[total.tone]}; font-size: {size}px; font-weight: {weight};"
            )
            value.setAlignment(_RIGHT)
            grid.addWidget(label, index, 0)
            grid.addWidget(value, index, 1)
        row.addLayout(grid)
        return row

    def _build_note(self, note: str) -> QLabel:
        label = QLabel(note)
        label.setWordWrap(True)
        label.setProperty("role", "cardNote")
        return label

    def _build_actions(self) -> QFrame:
        band = QFrame()
        band.setProperty("role", "cardFoot")
        row = QHBoxLayout(band)
        row.setContentsMargins(22, 12, 22, 12)
        row.setSpacing(8)

        close = QPushButton("Close")
        close.setProperty("variant", "outline")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        row.addStretch(1)

        save = QPushButton("Save as PDF")
        save.setProperty("variant", "outline")
        save.clicked.connect(self._save_pdf)
        row.addWidget(save)

        # Print is the primary action: a card is opened to be read, and the
        # next thing done with a read invoice is handing it over.
        print_button = QPushButton("Print")
        print_button.setProperty("variant", "primary")
        print_button.clicked.connect(self._print)
        row.addWidget(print_button)
        return band

    # ---------------- output ----------------

    def _save_pdf(self) -> None:
        save_pdf(self, self._card)

    def _print(self) -> None:
        print_card(self, self._card)


_TAG_TONES = {
    "ink": "info",
    "muted": "muted",
    "success": "success",
    "info": "info",
    "warning": "warning",
    "danger": "danger",
}
"""Card tones as the pill stylesheet names them. Only the neutral one
differs: a card's "ink" is a plain fact, and the pills have no plain
variant, so it borrows the informational one."""


def save_pdf(parent: QWidget, card: RecordCard) -> None:
    """Write `card` to a PDF, reporting either outcome to the user.

    Shared with the reports screen, which saves the same way without ever
    opening a card.
    """
    try:
        path = paper.save_pdf(parent, card)
    except OSError as error:
        QMessageBox.warning(parent, "Save as PDF", str(error))
        return
    if path is not None:
        QMessageBox.information(parent, "Saved", f"Saved to\n{path}")


def print_card(parent: QWidget, card: RecordCard) -> None:
    """Send `card` to a printer, reporting a failure to the user."""
    try:
        paper.print_card(parent, card)
    except OSError as error:  # pragma: no cover - depends on the print spooler
        QMessageBox.warning(parent, "Print", str(error))
