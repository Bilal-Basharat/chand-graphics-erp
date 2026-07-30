from __future__ import annotations

from app.application.dto.commands import CreateCardCommand
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.base import UseCase
from app.domain.entities.card import Card
from app.domain.uow import UnitOfWork

from app.application.auth.session import CurrentUserSession
from app.application.use_cases.authenticated_base import AuthenticatedUseCase

class CreateCardUseCase(AuthenticatedUseCase[CreateCardCommand, Card]):
    """
    Create a wedding card master record.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: CreateCardCommand) -> Card:

        current_user_id = self.current_user_id()

        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            cabinets = self.require(uow.cabinets, "cabinets")

            card_number = request.card_number.strip()
            name = request.name.strip()

            # created_by_user_id = request.created_by_user_id or self.current_user_id()

            if cards.get_by_card_number(card_number) is not None:
                raise DuplicateEntityError(f"Card '{card_number}' already exists")

            if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
                raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            card = Card(
                card_number=card_number,
                name=name,
                purchase_price=request.purchase_price,
                selling_price=request.selling_price,
                current_stock=request.current_stock,
                minimum_stock=request.minimum_stock,
                cabinet_id=request.cabinet_id,
                description=request.description,
                created_by_user_id=current_user_id,
            )

            return cards.add(card)


class ListCardsUseCase(AuthenticatedUseCase[int, list[Card]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[Card]:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            return cards.list(limit=request)

class GetCardByNumberUseCase(AuthenticatedUseCase[str, Card | None]):
    """
    Load one card by its business number.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> Card | None:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            return cards.get_by_card_number(request.strip())


class ListLowStockCardsUseCase(AuthenticatedUseCase[int, list[Card]]):
    """
    List cards whose stock is at or below minimum.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[Card]:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            return cards.list_low_stock(limit=request)