"""
Who to call when the application cannot help.

One assembly, shared by every screen that offers it, so the licence page,
the activation dialog and the sign-in screen cannot end up quoting
different numbers. Rows nobody filled in are left out entirely — a
support card offering a dash to ring is worse than one that is shorter.

Contact only. The build version is on the status bar of every screen
already, and the one identifier support actually asks for — the
installation ID — is on the screens that have it.
"""
from __future__ import annotations

from app.config.settings import AppSettings


def support_details(settings: AppSettings) -> list[tuple[str, str]]:
    """The developer's contact rows, in the order a card lists them."""
    rows = (
        ("Developed by", settings.developed_by),
        ("Email", settings.developer_email),
        ("Phone", settings.developer_contact),
    )
    return [(label, value) for label, value in rows if value]


def support_line(settings: AppSettings) -> str:
    """The same rows on one line, for somewhere a card will not fit.

    Empty when nothing was filled in, so a caller can leave the sentence
    out rather than trail off into a colon and nothing.
    """
    return " · ".join(value for _label, value in support_details(settings))
