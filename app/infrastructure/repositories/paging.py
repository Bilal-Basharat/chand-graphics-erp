"""
The four things every paged query does, written once.

Each repository still builds its own statement — which columns a term is
looked for in, which joins that needs, what a filter means — because that
is the part that genuinely differs per list. What does not differ is
matching a term across columns, ordering by a name the caller supplied,
and counting what the same conditions matched. Thirteen copies of those
would drift, and the one that drifts is a list that quietly disagrees with
its own page count.
"""
from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.orm import Session


def contains(term: str) -> str:
    """A term as a LIKE pattern: found anywhere in the value, not only at
    the start. A shopkeeper looking for "80 gsm art paper" types "gsm"."""
    return f"%{term.strip()}%"


def matching(pattern: str, *columns) -> ColumnElement[bool]:
    """True where any of these columns contains the pattern."""
    return or_(*(column.ilike(pattern) for column in columns))


def ordered(
    statement: Select,
    *,
    sortable: Mapping[str, object],
    field: str | None,
    desc: bool,
    default: str,
    default_desc: bool = False,
    tiebreak,
) -> Select:
    """Order by the field the caller named, if it is one this list offers.

    A name that is not in `sortable` falls back to the list's own order —
    and to that order's own direction, since "newest first" is what a
    document list means by unsorted. An unknown name is a screen asking
    for something this list does not have, not a reason to refuse a page.

    `tiebreak` is not optional and is the whole point of this function.
    Rows that tie on the sort column — the same name, the same timestamp —
    have no inherent order, so the database is free to return them in a
    different order for page two than it did for page one. Records then
    appear twice, or never, and it reads as data loss rather than as a
    missing ORDER BY.
    """
    column = sortable.get(field or "")
    if column is None:
        column, desc = sortable[default], default_desc
    if desc:
        return statement.order_by(column.desc(), tiebreak.desc())
    return statement.order_by(column.asc(), tiebreak.asc())


def total(session: Session, statement: Select) -> int:
    """How many rows the statement matches, without fetching them.

    Counted over the statement itself rather than over a hand-written
    repeat of its WHERE clause, so a filter can never be applied to the
    page and forgotten in the count.
    """
    return int(session.execute(select(func.count()).select_from(statement.subquery())).scalar_one())


def totals(session: Session, statement: Select, *columns):
    """Aggregates over exactly the rows a page was taken from.

    The projection is swapped and the conditions are kept, so a figure in
    a summary strip describes the same set the list does. Computed rather
    than added up from the rows on screen: "sold this month" is an answer
    about the month, and a page is a hundredth of it.
    """
    return session.execute(statement.with_only_columns(*columns)).one()
