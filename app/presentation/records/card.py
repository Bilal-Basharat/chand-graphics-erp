"""
What a record looks like when it is written out in full.

Every document this shop keeps reads the same way once it is on the page:
a heading naming what it is and how far along it is, a few facts about who
and when, one or more tables of lines, a column of totals, and a note at
the foot. An invoice, a purchase, a job order, an expense and a period
report differ in *which* facts and *which* tables — and that is data, not
structure.

So there is one card here rather than one per module, and rather than one
for documents and a second for payments. A payment is not a record of its
own: money paid against an invoice belongs underneath the invoice it
settles, which is why it appears below as a section of one and never as a
card.

The card is rendered twice — `dialogs/record_card_dialog.py` for the
screen, `records/paper.py` for print and PDF. Two renderings, not two
models: a card has to read well on a monitor and on A4, and those want
different type, spacing and colour for the same facts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.presentation.theme import tokens as t
from app.presentation.widgets.table_model import Alignment

Tone = Literal["ink", "muted", "success", "info", "warning", "danger"]
"""What a figure means, not what colour it is.

Named rather than given as hex because both renderings have to agree on
it, and paper is not a screen: a tone that reads well on a lit panel is
not always the one to put on white. Each side maps these to its own
palette — see `TONE_COLORS` and `paper.PAPER_TONES`.
"""

TONE_COLORS: dict[str, str] = {
    "ink": t.INK,
    "muted": t.MUTED,
    "success": t.SUCCESS,
    "info": t.INFO,
    "warning": t.WARNING,
    "danger": t.DANGER,
}


@dataclass(frozen=True, slots=True)
class Field:
    """One fact about the record: who it is for, when it was raised."""

    label: str
    value: str
    tone: Tone = "ink"


@dataclass(frozen=True, slots=True)
class Heading:
    """One column of a section's table."""

    title: str
    align: Alignment = "left"
    width: int | None = None
    """Fixed pixels on screen; unset columns share the leftover space, as
    they do in every other table in the app. Paper sizes itself."""


@dataclass(frozen=True, slots=True)
class Section:
    """A table of lines under a title — what was sold, what was paid."""

    title: str
    headings: tuple[Heading, ...]
    rows: tuple[tuple[str, ...], ...]
    empty: str = "Nothing recorded."


@dataclass(frozen=True, slots=True)
class Total:
    """One line of the money column at the foot of the card."""

    label: str
    value: str
    tone: Tone = "ink"
    strong: bool = False
    """The one figure the record comes down to. At most one per card —
    two things in bold is a card with no answer on it."""


@dataclass(frozen=True, slots=True)
class RecordCard:
    kind: str
    """What this is: "Sale invoice", "Job order", "Report"."""
    reference: str
    """What it is called: the invoice number, the expense's name."""
    subtitle: str = ""
    status: str = ""
    status_tone: Tone = "muted"
    fields: tuple[Field, ...] = ()
    sections: tuple[Section, ...] = ()
    totals: tuple[Total, ...] = ()
    note: str = ""

    @property
    def title(self) -> str:
        return f"{self.kind} {self.reference}".strip()

    @property
    def file_stem(self) -> str:
        """A filename for the PDF, safe on Windows and readable to a human.

        Anything that isn't a letter, digit, dot or dash becomes a single
        dash — invoice numbers and expense names both end up here, and an
        expense called "Ink / toner" would otherwise name a directory.
        """
        return re.sub(r"[^A-Za-z0-9.-]+", "-", self.title).strip("-") or "record"
