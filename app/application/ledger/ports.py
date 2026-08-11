"""
What a party ledger is made of, with no idea what a document is.

A ledger is two things: a party who starts with a balance, and a stream of
dated events that push that balance up or down. Which documents produce
those events is not the ledger's business, which is the point of the two
ports below — a build where *job orders* charge a customer rather than
sales writes one more `LedgerSource` and changes nothing else. The use
case, the running balance, the DTOs and the screen all stay as they are.

The two directions are named for what they do to the balance rather than
for accounting sides, because that stays true for both parties: a sale
charges a customer, a purchase charges you, and in both cases a payment
settles it. Debit and credit are *wording*, and the wording flips between
the two ledgers — so it is chosen where wording belongs, on the screen.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.domain.uow import UnitOfWork

ZERO = Decimal("0.00")


class LedgerDirection(StrEnum):
    CHARGE = "charge"
    """What the party owes goes up: a sale to them, a purchase from them."""

    PAYMENT = "payment"
    """...and back down: money received from them, or paid to them."""


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    """One dated movement on a party's account, whatever produced it."""

    occurred_at: datetime
    reference: str
    """The document it came from — an invoice or purchase number."""
    document_kind: str
    """Which family that document belongs to, in the source's own word.

    Carried so a screen can offer to open the document behind a line. It
    travels on the event rather than being assumed from which ledger is
    on screen, because one ledger may be fed by more than one source —
    which is the whole point of there being sources at all.
    """
    detail: str
    """What happened, in words: "Sale", "Payment received · Cash"."""
    amount: Decimal
    """Always positive. `direction` says which way it moves the balance."""
    direction: LedgerDirection


@dataclass(frozen=True, slots=True)
class LedgerParty:
    """Who a ledger is for, reduced to what a ledger needs.

    Deliberately not `Customer` or `Supplier`: the ledger works the same
    for both, and for whatever a later build adds.
    """

    id: int
    name: str
    opening_balance: Decimal


class PartyLookup(ABC):
    """Which list of parties a ledger is about."""

    @abstractmethod
    def find(self, uow: UnitOfWork, party_id: int) -> LedgerParty | None:
        raise NotImplementedError


class LedgerSource(ABC):
    """One family of documents that moves a party's account.

    Implementations are thin: they call repositories and shape the result
    into `LedgerEvent`s. They hold no state, so one instance is shared for
    the life of the application.
    """

    @abstractmethod
    def net_before(self, uow: UnitOfWork, party_id: int, before: datetime) -> Decimal:
        """This family's net effect on the balance before the window opens.

        Charges minus payments. It is what turns a party's lifetime
        opening balance into the opening balance for the period on screen,
        and it is an aggregate on purpose — those rows are never shown, so
        they are never loaded.
        """
        raise NotImplementedError

    @abstractmethod
    def events(
        self,
        uow: UnitOfWork,
        party_id: int,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[LedgerEvent]:
        """The lines this family contributes inside the window.

        Order does not matter — the ledger sorts everything it is given by
        date, because two sources cannot know about each other's dates.
        """
        raise NotImplementedError
