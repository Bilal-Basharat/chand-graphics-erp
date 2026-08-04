from __future__ import annotations

import re

_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
"""Deliberately loose. The only proof an address works is a message
arriving at it, so this rejects what is obviously not an address —
missing @, spaces, no domain — and leaves the rest to delivery."""

MAX_LENGTH = 255
"""Matches the users table's column, so an over-long address is refused
with a sentence rather than a database error."""


def clean_email(value: str) -> str:
    """Trim and lowercase an address that is being *looked up*.

    Deliberately does no format checking. What is already stored is the
    address, whatever it looks like — the initial admin account ships as
    `admin@localhost`, which has no dotted domain and is still the address
    that account signs in with. Refusing to look it up would mean the one
    account every installation starts with could never be recovered.

    Raises:
        ValueError: if nothing was typed.
    """
    email = value.strip().lower()
    if not email:
        raise ValueError("Enter an email address.")
    return email


def normalize_email(value: str) -> str:
    """Clean an address that is being *set*, rejecting what cannot be one.

    Stricter than `clean_email` because this one has to be deliverable:
    it is about to become somebody's sign-in name and the place their
    password reset would be sent.

    Raises:
        ValueError: if the address is empty or malformed.
    """
    email = clean_email(value)

    if len(email) > MAX_LENGTH:
        raise ValueError("That email address is too long.")
    if not _PATTERN.match(email):
        raise ValueError(f"'{value.strip()}' is not a valid email address.")

    return email
