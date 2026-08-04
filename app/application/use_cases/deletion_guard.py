"""
One phrasing for "this record is still referenced".

Cards, inventory items, cabinets, payment methods and expense categories
can all be deleted now, and each of them is pointed at by a different set
of documents. What differs between the five is only which references are
counted; the decision, and the sentence the user reads when it goes
against them, should not be written out five times.
"""
from __future__ import annotations

from app.application.exceptions import EntityInUseError


def ensure_not_in_use(name: str, usage: dict[str, int]) -> None:
    """Refuse a delete while anything still points at the record.

    `usage` maps a singular noun to how many of those reference it, e.g.
    `{"sale": 3, "purchase": 0}`. Zero counts are dropped here, so callers
    can pass every reference they checked without filtering first.
    """
    held_by = [
        f"{count} {noun}" if count == 1 else f"{count} {noun}s"
        for noun, count in usage.items()
        if count
    ]
    if not held_by:
        return
    raise EntityInUseError(
        f"'{name}' is still used by {_and_list(held_by)} and cannot be deleted. "
        "Remove or reassign those records first."
    )


def _and_list(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"
