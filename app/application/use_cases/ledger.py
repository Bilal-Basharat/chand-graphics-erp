"""
The running balance, computed in one place for every kind of ledger.

There is one use case here rather than one per party. A customer ledger
and a supplier ledger differ only in *which* parties they look up and
*which* documents they read, and both of those arrive as constructor
arguments — see `app.application.ledger.ports`. The arithmetic below is
the same either way, which is the whole reason it is written once.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.auth.session import CurrentUserSession
from app.application.dto.queries import LedgerLine, LedgerQuery, PartyLedger
from app.application.exceptions import NotFoundError
from app.application.ledger.ports import (
    ZERO,
    LedgerDirection,
    LedgerEvent,
    LedgerParty,
    LedgerSource,
    PartyLookup,
)
from app.application.use_cases.authorized_base import AuthorizedUnitOfWorkUseCase
from app.domain.uow import UnitOfWork


def build_ledger(
    party: LedgerParty,
    opening_balance: Decimal,
    events: Iterable[LedgerEvent],
) -> PartyLedger:
    """Walk a party's events in date order, carrying the balance along.

    Pure: no repositories, no session, no party type. Everything the
    ledger means comes down to this loop, so it is the thing worth
    testing.
    """
    balance = opening_balance
    total_charges = ZERO
    total_payments = ZERO
    lines: list[LedgerLine] = []

    for event in sorted(events, key=lambda item: item.occurred_at):
        charged = event.amount if event.direction is LedgerDirection.CHARGE else ZERO
        paid = event.amount if event.direction is LedgerDirection.PAYMENT else ZERO

        balance = balance + charged - paid
        total_charges += charged
        total_payments += paid

        lines.append(
            LedgerLine(
                occurred_at=event.occurred_at,
                reference=event.reference,
                detail=event.detail,
                document_kind=event.document_kind,
                charge=charged,
                payment=paid,
                balance=balance,
            )
        )

    return PartyLedger(
        party_id=party.id,
        party_name=party.name,
        opening_balance=opening_balance,
        lines=tuple(lines),
        total_charges=total_charges,
        total_payments=total_payments,
        closing_balance=balance,
    )


class GetPartyLedgerUseCase(AuthorizedUnitOfWorkUseCase[LedgerQuery, PartyLedger]):
    """One party's account over one period.

    Assembled in the container: which parties, and which document
    families move them. Nothing here names a sale or a purchase.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
        *,
        party: PartyLookup,
        sources: Sequence[LedgerSource],
    ) -> None:
        super().__init__(uow, current_user_session, authorization_service)
        self.party = party
        self.sources = tuple(sources)

    def execute(self, request: LedgerQuery) -> PartyLedger:
        self.require_permission(Permission.VIEW_REPORTS)

        with self.uow as uow:
            party = self.party.find(uow, request.party_id)
            if party is None:
                raise NotFoundError(f"Party id={request.party_id} not found")

            # Everything before the window, as one figure per source, on
            # top of what the party owed before any of it was recorded.
            opening_balance = party.opening_balance + sum(
                (source.net_before(uow, party.id, request.start) for source in self.sources),
                ZERO,
            )

            events = [
                event
                for source in self.sources
                for event in source.events(
                    uow, party.id, request.start, request.end, request.limit
                )
            ]

            return build_ledger(party, opening_balance, events)
