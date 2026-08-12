"""
Where this build's ageing reports get their documents.

Two lines each, and the only code that knows receivables are made of
invoices and payables of purchase bills. Everything above this file works
in `OutstandingRow`s and cannot tell the two apart.
"""
from __future__ import annotations

from datetime import datetime

from app.application.reporting.ports import OutstandingSource
from app.application.use_cases.base import UseCase
from app.domain.repositories.aggregates import OutstandingRow
from app.domain.uow import UnitOfWork


class ReceivablesSource(OutstandingSource):
    """Invoices customers have not finished paying."""

    def documents(self, uow: UnitOfWork, as_at: datetime) -> list[OutstandingRow]:
        sales = UseCase.require(uow.sales, "sales")
        return sales.outstanding_before(as_at)


class PayablesSource(OutstandingSource):
    """Bills the shop has not finished paying."""

    def documents(self, uow: UnitOfWork, as_at: datetime) -> list[OutstandingRow]:
        purchases = UseCase.require(uow.purchases, "purchases")
        return purchases.outstanding_before(as_at)
