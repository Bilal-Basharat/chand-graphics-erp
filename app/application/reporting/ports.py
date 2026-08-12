"""
Where an ageing report gets its unpaid documents.

The same arrangement as the ledger's sources, and for the same reason:
"what is still owed, and how long has it been owed" is one question, and
whether it is asked of invoices or of bills is a matter of which documents
are handed over. A build where job orders carry the debt writes one more
source and changes nothing else.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.repositories.aggregates import OutstandingRow
from app.domain.uow import UnitOfWork


class OutstandingSource(ABC):
    """One family of documents that can still be owing."""

    @abstractmethod
    def documents(self, uow: UnitOfWork, as_at: datetime) -> list[OutstandingRow]:
        """Everything of this kind with money left on it, as at a moment.

        Unbounded on purpose: a debt left off a list of debts is the one
        that never gets chased. The set is naturally small — it is only
        what is unpaid.
        """
        raise NotImplementedError
