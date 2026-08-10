from __future__ import annotations

from app.application.auth.session import CurrentUserSession
from app.application.dto.queries import SearchQuery
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.domain.entities.inventory_item import InventoryItem
from app.domain.entities.purchase import Purchase
from app.domain.entities.sale import Sale
from app.domain.uow import UnitOfWork


class SearchInventoryItemsUseCase(AuthenticatedUseCase[SearchQuery, list[InventoryItem]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: SearchQuery) -> list[InventoryItem]:
        term = request.term.strip()
        if not term:
            return []

        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.search_by_term(term, request.limit)


class SearchPurchasesUseCase(AuthenticatedUseCase[SearchQuery, list[Purchase]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: SearchQuery) -> list[Purchase]:
        term = request.term.strip()
        if not term:
            return []

        with self.uow as uow:
            purchases = self.require(uow.purchases, "purchases")
            return purchases.search_by_term(term, request.limit)


class SearchSalesUseCase(AuthenticatedUseCase[SearchQuery, list[Sale]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: SearchQuery) -> list[Sale]:
        term = request.term.strip()
        if not term:
            return []

        with self.uow as uow:
            sales = self.require(uow.sales, "sales")
            return sales.search_by_term(term, request.limit)