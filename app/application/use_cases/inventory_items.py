from __future__ import annotations

from app.application.dto.commands import (
    CreateInventoryItemCommand,
)

from app.domain.entities.inventory_item import InventoryItem
from app.domain.uow import UnitOfWork

from app.application.exceptions import DuplicateEntityError, NotFoundError

from app.application.auth.session import CurrentUserSession
from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import AuthorizedUseCase

class CreateInventoryItemUseCase(AuthorizedUseCase[CreateInventoryItemCommand, InventoryItem]):
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

    def execute(self, request: CreateInventoryItemCommand) -> InventoryItem:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")

            name = request.name.strip()
            if items.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Inventory item '{name}' already exists")

            item = InventoryItem(
                name=name,
                purchase_price=request.purchase_price,
                selling_price=request.selling_price,
                current_stock=request.current_stock,
                minimum_stock=request.minimum_stock,
                description=request.description,
                created_by_user_id=current_user_id
            )
            return items.add(item)


class ListInventoryItemsUseCase(AuthenticatedUseCase[int, list[InventoryItem]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[InventoryItem]:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.list(limit=request)


class GetInventoryItemByNameUseCase(AuthenticatedUseCase[str, InventoryItem | None]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: str) -> InventoryItem | None:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.get_by_name(request.strip())


class ListLowStockInventoryItemsUseCase(AuthenticatedUseCase[int, list[InventoryItem]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[InventoryItem]:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.list_low_stock(limit=request)