from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class SearchQuery:
    term: str
    limit: int = 50


@dataclass(slots=True)
class LedgerQuery:
    party_id: int
    start: datetime
    end: datetime
    limit: int = 500


@dataclass(frozen=True, slots=True)
class LedgerLine:
    """One row of a party's statement, with the balance it left behind.

    `charge` and `payment` are named for what they do to the balance, not
    for an accounting side: the same line is a debit on a customer's
    statement and a credit on a supplier's. Only one of the two is ever
    non-zero.
    """

    occurred_at: datetime
    reference: str
    detail: str
    document_kind: str
    """Which family of document this line came from, so a screen can open
    it. Set by the source that produced it — see
    `app.application.ledger.sources`."""
    charge: Decimal
    payment: Decimal
    balance: Decimal


@dataclass(frozen=True, slots=True)
class PartyLedger:
    """A customer's or supplier's account over one period."""

    party_id: int
    party_name: str
    opening_balance: Decimal
    """As at the start of the period — the party's own opening balance
    plus everything that happened before it."""
    lines: tuple[LedgerLine, ...]
    total_charges: Decimal
    total_payments: Decimal
    closing_balance: Decimal
    """What is outstanding at the end. Positive means the party owes:
    money to collect on a customer's ledger, money to pay on a
    supplier's."""


@dataclass(slots=True)
class PurchasePaymentStatus:
    purchase_id: int
    grand_total: Decimal
    paid_amount: Decimal
    balance_amount: Decimal


@dataclass(slots=True)
class SalePaymentStatus:
    sale_id: int
    grand_total: Decimal
    paid_amount: Decimal
    balance_amount: Decimal