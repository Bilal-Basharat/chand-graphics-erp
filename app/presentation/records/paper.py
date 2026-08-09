"""
A record card on paper: the PDF, and the print job.

Both come from one HTML document rather than from a widget screenshot,
because paper is not a screen. A4 has a fixed width, no scrollbar and no
hover, and it is read at arm's length in black on white — so the page
here sets its own type, spacing and palette, and the card model decides
what goes on it. Printing what the dialog shows would put a screen's
proportions on a page and a shop's letterhead nowhere.

The letterhead is the one thing on the page that is not in the card: it
is the same for every record the installation ever prints, so it is
carried here and refreshed whenever the company settings are saved,
rather than threaded through every screen that can open a card.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape

from app.shared.datetimes import now_pkt
from pathlib import Path

from PySide6.QtCore import QMarginsF, QStandardPaths
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QDialog, QFileDialog, QWidget

from app.presentation.formatting import date_time
from app.presentation.records.card import RecordCard, Section, Total
from app.presentation.theme import tokens as t

# Print colours, not screen ones. The screen's accents are tuned for a lit
# panel; on white paper — and worse, on a mono laser printer — the same
# reds and greens come out as indistinguishable mid-greys, so these are
# darker and further apart.
PAPER_TONES: dict[str, str] = {
    "ink": "#111111",
    "muted": "#666666",
    "success": "#12703a",
    "info": "#1a3fa8",
    "warning": "#9a4106",
    "danger": "#a81b1b",
}

_RULE = "#d4d7dd"
_BAND = "#f2f3f6"

_STYLE = f"""
body {{ color: {PAPER_TONES["ink"]}; }}
.brand {{ font-size: 15pt; font-weight: 600; }}
.brandline {{ font-size: 8pt; color: {PAPER_TONES["muted"]}; }}
.kind {{ font-size: 8pt; color: {PAPER_TONES["muted"]}; }}
.reference {{ font-size: 15pt; font-weight: 600; }}
.subtitle {{ font-size: 9pt; color: {PAPER_TONES["muted"]}; }}
.status {{ font-size: 9pt; font-weight: 600; }}
.section {{ font-size: 10pt; font-weight: 600; }}
.label {{ font-size: 7.5pt; color: {PAPER_TONES["muted"]}; }}
.value {{ font-size: 9.5pt; }}
th {{ font-size: 7.5pt; color: {PAPER_TONES["muted"]}; background-color: {_BAND}; }}
td {{ font-size: 9pt; }}
.total {{ font-size: 9.5pt; }}
.grand {{ font-size: 12pt; font-weight: 600; }}
.note {{ font-size: 9pt; color: {PAPER_TONES["muted"]}; }}
.foot {{ font-size: 9pt; color: {PAPER_TONES["muted"]}; text-align: right; line-height: 1.5; margin-top: 12px; }}
"""

_FIELDS_PER_ROW = 4
"""Facts across the top of the page. Four, as on screen, so a record that
is read and then printed does not rearrange itself between the two."""


def _rule() -> str:
    """A horizontal rule.

    Not `<hr>`: Qt's rich-text engine lays one out and then draws nothing,
    which is a gap where a line should be. A table row one point tall with
    a background is a line, on every renderer.
    """
    return (
        f'<table width="100%" cellspacing="0" cellpadding="0" '
        f'style="background-color: {_RULE};">'
        '<tr><td style="font-size: 1pt;">&nbsp;</td></tr></table>'
    )


@dataclass(frozen=True, slots=True)
class Letterhead:
    name: str
    address: str = ""
    contact: str = ""
    footer: str = ""


_DEFAULT = Letterhead(name="Chand Graphics")
_letterhead = _DEFAULT
_developer_info = ""  # New global variable for developer info

def set_company(settings) -> None:
    """Take the letterhead from the saved company settings.

    Called once when the shell opens and again whenever the settings are
    saved, so a page printed after a change carries the new details. A
    `None` — an installation whose settings have never been filled in —
    falls back to the shop's name alone rather than printing a page with
    no heading at all.
    """
    global _letterhead
    if settings is None:
        _letterhead = _DEFAULT
        return
    contact = " • ".join(part for part in (settings.phone, settings.email) if part)
    _letterhead = Letterhead(
        name=settings.company_name or _DEFAULT.name,
        address=settings.address or "",
        contact=contact,
        footer=settings.invoice_footer or "",
    )


def set_app_settings(settings) -> None:
    """Take the developer info from the app settings.
    Called once when the shell opens.
    """
    global _developer_info
    if settings is None:
        _developer_info = ""
        return
    
    parts = []
    if getattr(settings, "developed_by", ""):
        parts.append(settings.developed_by)
    if getattr(settings, "developer_email", ""):
        parts.append(settings.developer_email)
    if getattr(settings, "developer_contact", ""):
        parts.append(settings.developer_contact)
        
    # Format: "Developed by: Alvi-Systems | bilalbisharat@gmail.com | 03042602360"
    if parts:
        _developer_info = "Developed by: " + " | ".join(parts)
    else:
        _developer_info = ""


def letterhead() -> Letterhead:
    return _letterhead


# ---------------------------------------------------------------- html


# Rows separated by a hairline under each cell rather than boxed in a
# grid — the same treatment the tables on screen get, and one less thing
# between the reader and the figures.
_ROW_CELL = f'border-bottom: 1px solid {_RULE};'
_HEAD_CELL = f'background-color: {_BAND}; border-bottom: 1px solid {PAPER_TONES["muted"]};'


def _cell(text: str, align: str) -> str:
    return f'<td align="{align}" class="value" style="{_ROW_CELL}">{escape(text)}</td>'


def _head(card: RecordCard) -> str:
    company = _letterhead
    left = [f'<span class="brand">{escape(company.name)}</span>']
    for line in (company.address, company.contact):
        if line:
            left.append(f'<br><span class="brandline">{escape(line)}</span>')

    right = [
        f'<span class="kind">{escape(card.kind.upper())}</span>',
        f'<br><span class="reference">{escape(card.reference)}</span>',
    ]
    if card.subtitle:
        right.append(f'<br><span class="subtitle">{escape(card.subtitle)}</span>')
    if card.status:
        color = PAPER_TONES[card.status_tone]
        right.append(
            f'<br><span class="status" style="color: {color};">{escape(card.status)}</span>'
        )

    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td width="55%" valign="top">{"".join(left)}</td>'
        f'<td width="45%" valign="top" align="right">{"".join(right)}</td>'
        "</tr></table>"
        f"{_rule()}"
    )


def _fields(card: RecordCard) -> str:
    if not card.fields:
        return ""
    cells = [
        f'<td width="{100 // _FIELDS_PER_ROW}%" valign="top">'
        f'<span class="label">{escape(field.label.upper())}</span><br>'
        f'<span class="value" style="color: {PAPER_TONES[field.tone]};">'
        f"{escape(field.value)}</span></td>"
        for field in card.fields
    ]
    rows = [
        "<tr>" + "".join(cells[start:start + _FIELDS_PER_ROW]) + "</tr>"
        for start in range(0, len(cells), _FIELDS_PER_ROW)
    ]
    return f'<table width="100%" cellspacing="0" cellpadding="5">{"".join(rows)}</table>'


def _section(section: Section) -> str:
    header = "".join(
        f'<th align="{heading.align}" style="{_HEAD_CELL}">{escape(heading.title)}</th>'
        for heading in section.headings
    )
    if section.rows:
        body = "".join(
            "<tr>"
            + "".join(
                _cell(value, heading.align) for heading, value in zip(section.headings, row)
            )
            + "</tr>"
            for row in section.rows
        )
    else:
        body = (
            f'<tr><td colspan="{len(section.headings)}" class="label" '
            f'style="{_ROW_CELL}">{escape(section.empty)}</td></tr>'
        )
    return (
        f'<p class="section">{escape(section.title)}</p>'
        f'<table width="100%" cellspacing="0" cellpadding="5">'
        f"<tr>{header}</tr>{body}</table>"
    )


def _totals(totals: tuple[Total, ...]) -> str:
    if not totals:
        return ""
    rows = "".join(
        f'<tr><td align="right" class="{"grand" if total.strong else "total"}" '
        f'style="color: {PAPER_TONES["muted"]};">{escape(total.label)}</td>'
        f'<td align="right" width="40%" class="{"grand" if total.strong else "total"}" '
        f'style="color: {PAPER_TONES[total.tone]};">{escape(total.value)}</td></tr>'
        for total in totals
    )
    # An empty left cell pushes the block to the right margin, where every
    # printed invoice puts its money column.
    return (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        '<td width="55%"></td><td width="45%">'
        f'<table width="100%" cellspacing="0" cellpadding="4">{rows}</table>'
        "</td></tr></table>"
    )


def card_html(card: RecordCard) -> str:
    """The whole page, as rich text QTextDocument can lay out and paginate."""
    parts = [_head(card), _fields(card)]
    parts.extend(_section(section) for section in card.sections)
    parts.append(_totals(card.totals))
    if card.note:
        parts.append(f'<p class="note">{escape(card.note)}</p>')
        
        
    foot_date = f"Printed {date_time(datetime.now())}"
    
    # Build the footer blocks sequentially so they naturally fall on separate lines
    footer_blocks = [f'{_rule()}']
    
    # 1. Custom invoice footer from company settings (if any)
    if _letterhead.footer:
        footer_blocks.append(f'<p align="center" class="foot">{escape(_letterhead.footer)}</p>')
        
    # 2. Line 1: The Date (Centered)
    footer_blocks.append(f'<p align="center" class="foot">{escape(foot_date)}</p>')
    
    # 3. Line 2: The Developer Info (Right-aligned)
    if _developer_info:
        footer_blocks.append(f'<p align="right" class="foot">{escape(_developer_info)}</p>')

    parts.append("".join(footer_blocks))
    return f"<html><body>{''.join(parts)}</body></html>"


# ---------------------------------------------------------------- output


def _printer() -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(14, 14, 14, 16), QPageLayout.Unit.Millimeter)
    return printer


def _document(card: RecordCard) -> QTextDocument:
    document = QTextDocument()
    document.setDefaultFont(QFont(t.FONT_FAMILY, 9))
    document.setDefaultStyleSheet(_STYLE)
    document.setHtml(card_html(card))
    return document


def suggested_path(card: RecordCard) -> str:
    documents = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    return str(Path(documents or ".") / f"{card.file_stem}.pdf")


def save_pdf(parent: QWidget, card: RecordCard) -> str | None:
    """Write the card to a PDF the user picks. None if they cancelled.

    Raises OSError when the file did not appear — QPrinter reports a
    failed write by simply not writing, and a "Saved" message over a
    missing file is worse than an error.
    """
    path, _filter = QFileDialog.getSaveFileName(
        parent, f"Save {card.title} as PDF", suggested_path(card), "PDF document (*.pdf)"
    )
    if not path:
        return None
    if not path.lower().endswith(".pdf"):
        path += ".pdf"

    printer = _printer()
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(path)
    _document(card).print_(printer)

    written = Path(path)
    if not written.exists() or written.stat().st_size == 0:
        raise OSError(f"Could not write {path}. Check the folder is writable.")
    return path


def print_card(parent: QWidget, card: RecordCard) -> bool:
    """Send the card to a printer the user picks. False if they cancelled."""
    printer = _printer()
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle(f"Print {card.title}")
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    _document(card).print_(printer)
    return True
