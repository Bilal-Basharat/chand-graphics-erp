"""
Putting seeded rows on the dates they are supposed to have happened.

No use case takes "record this as of last March", and none should: the
app stamps a document when it is raised, which is right for a shop and
useless for testing a period selector, a ledger or a report. So rows are
created normally and their dates are corrected afterwards.

This is the only module in the seeder that writes SQL. It is kept apart
so that the one place bypassing the application layer is obvious, small,
and easy to check. It touches date columns and nothing else.

Dates are collected while seeding and written in one pass at the end, so
the run is one extra transaction rather than one per document.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Engine, text


@dataclass(frozen=True, slots=True)
class _DocumentTables:
    """A document and the payments hanging off it."""

    table: str
    payments_table: str
    payments_key: str
    paid_column: str


SALE = _DocumentTables("sales", "sale_payments", "sale_id", "received_at")
PURCHASE = _DocumentTables("purchases", "purchase_payments", "purchase_id", "paid_at")

SALE_RETURN = "sale_returns"
PURCHASE_RETURN = "purchase_returns"
"""Return tables, dated by `row()` on their own `returned_at` column.

Not `_DocumentTables`: a return has no payments hanging off it — the
money that went back with it is a column on the return itself.
"""


@dataclass(slots=True)
class Backdater:
    """Remembers when each seeded row really happened, then writes it."""

    _rows: list[tuple[str, int, datetime, tuple[str, ...]]] = field(default_factory=list)
    _documents: list[tuple[_DocumentTables, int, datetime, tuple[datetime, ...]]] = field(
        default_factory=list
    )

    def row(self, table: str, row_id: int, when: datetime, *also: str) -> None:
        """Date one row: `created_at`, plus any other date column it has."""
        self._rows.append((table, row_id, when, also))

    def document(
        self,
        tables: _DocumentTables,
        document_id: int,
        when: datetime,
        payment_dates: Sequence[datetime],
    ) -> None:
        """Date a sale or purchase and each payment recorded against it.

        Payments are matched to dates in the order they were created,
        which is the order they were listed in the dataset.
        """
        self._documents.append((tables, document_id, when, tuple(payment_dates)))

    def apply(self, engine: Engine) -> int:
        """Write every remembered date. Returns how many rows were dated."""
        dated = 0
        with engine.begin() as connection:
            for table, row_id, when, also in self._rows:
                _stamp(connection, table, row_id, when, also)
                dated += 1
            for tables, document_id, when, payment_dates in self._documents:
                _stamp(connection, tables.table, document_id, when, ())
                dated += 1 + _stamp_payments(connection, tables, document_id, payment_dates)
        return dated


def _stamp(connection, table: str, row_id: int, when: datetime, also: tuple[str, ...]) -> None:
    # Written with text() rather than a Table update so that SQLAlchemy's
    # `onupdate` on updated_at does not fire: a seeded row was never
    # edited, and saying it was would show up on screen.
    columns = ", ".join(f"{column} = :when" for column in ("created_at", *also))
    connection.execute(
        text(f"UPDATE {table} SET {columns} WHERE id = :row_id"),
        {"when": when, "row_id": row_id},
    )


def _stamp_payments(
    connection,
    tables: _DocumentTables,
    document_id: int,
    payment_dates: tuple[datetime, ...],
) -> int:
    if not payment_dates:
        return 0

    ids = connection.execute(
        text(f"SELECT id FROM {tables.payments_table} WHERE {tables.payments_key} = :id ORDER BY id"),
        {"id": document_id},
    ).scalars().all()

    if len(ids) != len(payment_dates):
        raise RuntimeError(
            f"{tables.table} id={document_id} has {len(ids)} payments but "
            f"{len(payment_dates)} dates to give them"
        )

    for payment_id, when in zip(ids, payment_dates, strict=True):
        _stamp(connection, tables.payments_table, payment_id, when, (tables.paid_column,))
    return len(ids)
