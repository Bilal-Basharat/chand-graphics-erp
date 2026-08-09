from __future__ import annotations

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    UpdateInventoryItemCommand,
)

from app.domain.entities.inventory_item import InventoryItem
from app.domain.enums.item_type import ItemType
from app.domain.uow import UnitOfWork

from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.deletion_guard import ensure_not_in_use

from app.application.auth.session import CurrentUserSession
from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import (
    AuthorizedUnitOfWorkUseCase,
    AuthorizedUseCase,
)

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

        if request.current_stock != 0:
            raise ValueError("New items must start with zero stock; stock is set by recording a purchase.")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")

            name = request.name.strip()
            if items.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Inventory item '{name}' already exists")

            item = InventoryItem(
                name=name,
                current_stock=request.current_stock,
                minimum_stock=request.minimum_stock,
                description=request.description,
                unit=request.unit,
                created_by_user_id=current_user_id
            )
            return items.add(item)


class UpdateInventoryItemUseCase(AuthorizedUnitOfWorkUseCase[UpdateInventoryItemCommand, InventoryItem]):
    """Correct an item's catalogue details. Stock is untouched — it is the
    result of purchases, sales and adjustments, not a field to type over."""

    def execute(self, request: UpdateInventoryItemCommand) -> InventoryItem:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        current_user_id = self.current_user_id()

        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")

            item = items.get_by_id(request.id)
            if item is None:
                raise NotFoundError(f"Inventory item id={request.id} not found")

            name = request.name.strip()
            clash = items.get_by_name(name)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Inventory item '{name}' already exists")

            item.name = name
            item.minimum_stock = request.minimum_stock
            item.description = request.description
            item.unit = request.unit
            item.updated_by_user_id = current_user_id

            return items.update(item)


class DeleteInventoryItemUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """Remove an item, unless it has been bought or sold — see
    `DeleteCardUseCase` for why that is refused rather than cascaded."""

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            sales = self.require(uow.sales, "sales")
            purchases = self.require(uow.purchases, "purchases")
            jobs = self.require(uow.jobs, "jobs")

            item = items.get_by_id(request)
            if item is None:
                raise NotFoundError(f"Inventory item id={request} not found")

            ensure_not_in_use(
                item.name,
                {
                    "sale": sales.count_by_item(ItemType.INVENTORY_ITEM, request),
                    "purchase": purchases.count_by_item(ItemType.INVENTORY_ITEM, request),
                    "job": jobs.count_by_material(ItemType.INVENTORY_ITEM, request),
                },
            )

            items.delete(request)


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