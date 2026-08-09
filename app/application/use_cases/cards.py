from __future__ import annotations

from app.application.dto.commands import (
    CreateCardCommand,
    UpdateCardCabinetCommand,
    UpdateCardCommand,
)
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.base import UseCase
from app.application.use_cases.deletion_guard import ensure_not_in_use
from app.domain.entities.card import Card
from app.domain.enums.item_type import ItemType
from app.domain.uow import UnitOfWork

from app.application.auth.session import CurrentUserSession
from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import (
    AuthorizedUnitOfWorkUseCase,
    AuthorizedUseCase,
)

class CreateCardUseCase(AuthorizedUseCase[CreateCardCommand, Card]):
    """
    Create a wedding card master record.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: CreateCardCommand) -> Card:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        if request.current_stock != 0:
            raise ValueError("New cards must start with zero stock; stock is set by recording a purchase.")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            cabinets = self.require(uow.cabinets, "cabinets")

            card_number = request.card_number.strip()
            name = request.name.strip() if request.name else None

            if cards.get_by_card_number(card_number) is not None:
                raise DuplicateEntityError(f"Card '{card_number}' already exists")

            if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
                raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            card = Card(
                card_number=card_number,
                name=name,
                current_stock=request.current_stock,
                minimum_stock=request.minimum_stock,
                cabinet_id=request.cabinet_id,
                description=request.description,
                created_by_user_id=current_user_id,
            )

            return cards.add(card)


class UpdateCardCabinetUseCase(AuthorizedUseCase[UpdateCardCabinetCommand, Card]):
    """
    Move a card to a different cabinet (or unassign it, cabinet_id=None).
    """

    def __init__(
        self,
        uow: UnitOfWork,
        current_user_session: CurrentUserSession | None = None,
        authorization_service: AuthorizationService | None = None,
    ) -> None:
        if current_user_session is None:
            current_user_session = CurrentUserSession()
        if authorization_service is None:
            authorization_service = AuthorizationService(current_user_session)
        super().__init__(current_user_session, authorization_service)
        self.uow = uow

    def execute(self, request: UpdateCardCabinetCommand) -> Card:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            cabinets = self.require(uow.cabinets, "cabinets")

            card = cards.get_by_id(request.card_id)
            if card is None:
                raise NotFoundError(f"Card id={request.card_id} not found")

            if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
                raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            card.cabinet_id = request.cabinet_id
            return cards.update(card)


class UpdateCardUseCase(AuthorizedUnitOfWorkUseCase[UpdateCardCommand, Card]):
    """
    Correct a card's catalogue details.

    Stock is left exactly as it is: it is the running result of purchases,
    sales and adjustments, and this form is not one of them.
    """

    def execute(self, request: UpdateCardCommand) -> Card:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            cabinets = self.require(uow.cabinets, "cabinets")

            card = cards.get_by_id(request.id)
            if card is None:
                raise NotFoundError(f"Card id={request.id} not found")

            card_number = request.card_number.strip()
            clash = cards.get_by_card_number(card_number)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Card '{card_number}' already exists")

            if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
                raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            card.card_number = card_number
            card.name = request.name.strip() if request.name else None
            card.minimum_stock = request.minimum_stock
            card.cabinet_id = request.cabinet_id
            card.description = request.description
            card.updated_by_user_id = current_user_id

            return cards.update(card)


class DeleteCardUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """
    Remove a card, unless it has been bought or sold.

    Those documents record what was traded at what price. Deleting the
    card they name would leave them describing something that no longer
    exists, so the caller is told what is holding it instead.
    """

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            sales = self.require(uow.sales, "sales")
            purchases = self.require(uow.purchases, "purchases")
            jobs = self.require(uow.jobs, "jobs")

            card = cards.get_by_id(request)
            if card is None:
                raise NotFoundError(f"Card id={request} not found")

            ensure_not_in_use(
                card.card_number,
                {
                    "sale": sales.count_by_item(ItemType.CARD, request),
                    "purchase": purchases.count_by_item(ItemType.CARD, request),
                    "job": jobs.count_by_material(ItemType.CARD, request),
                },
            )

            cards.delete(request)


class ListCardsUseCase(AuthenticatedUseCase[int, list[Card]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[Card]:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            return cards.list(limit=request)


class ListCardsByCabinetUseCase(AuthenticatedUseCase[int, list[Card]]):
    """
    List the cards stored in a given cabinet.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int) -> list[Card]:
        with self.uow as uow:
            cards = self.require(uow.cards, "cards")
            return cards.list_by_cabinet_id(request)

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