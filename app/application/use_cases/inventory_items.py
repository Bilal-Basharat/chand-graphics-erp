from __future__ import annotations

from collections.abc import Collection

from app.application.dto.commands import (
    CreateInventoryItemCommand,
    UpdateInventoryItemCommand,
)
from app.application.dto.queries import InventoryPageQuery, PageResult

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
            cabinets = self.require(uow.cabinets, "cabinets")

            name = request.name.strip()
            if items.get_by_name(name) is not None:
                raise DuplicateEntityError(f"Inventory item '{name}' already exists")

            if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
                raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            item = InventoryItem(
                name=name,
                current_stock=request.current_stock,
                minimum_stock=request.minimum_stock,
                description=request.description,
                cabinet_id=request.cabinet_id,
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
            cabinets = self.require(uow.cabinets, "cabinets")

            item = items.get_by_id(request.id)
            if item is None:
                raise NotFoundError(f"Inventory item id={request.id} not found")

            name = request.name.strip()
            clash = items.get_by_name(name)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Inventory item '{name}' already exists")

            if request.cabinet_id is not None and cabinets.get_by_id(request.cabinet_id) is None:
                raise NotFoundError(f"Cabinet id={request.cabinet_id} not found")

            item.name = name
            item.minimum_stock = request.minimum_stock
            item.description = request.description
            item.cabinet_id = request.cabinet_id
            item.unit = request.unit
            item.updated_by_user_id = current_user_id

            return items.update(item)


class DeleteInventoryItemUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    """Remove an item, unless it has been bought or sold.

    Those documents record what was traded at what price. Deleting the
    item they name would leave them describing something that no longer
    exists, so the caller is told what is holding it instead."""

    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            sales = self.require(uow.sales, "sales")
            purchases = self.require(uow.purchases, "purchases")

            item = items.get_by_id(request)
            if item is None:
                raise NotFoundError(f"Inventory item id={request} not found")

            ensure_not_in_use(
                item.name,
                {
                    "sale": sales.count_by_item(ItemType.INVENTORY_ITEM, request),
                    "purchase": purchases.count_by_item(ItemType.INVENTORY_ITEM, request),
                },
            )

            items.delete(request)


class PageInventoryItemsUseCase(AuthenticatedUseCase[InventoryPageQuery, PageResult]):
    """One page of the catalogue, as a screen asks for it.

    The page and the count run inside one unit of work, so a record added
    between the two cannot leave a list of a hundred rows claiming to be a
    hundred and one.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: InventoryPageQuery) -> PageResult:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            rows = items.page_items(
                search=request.search,
                stock=request.stock,
                sort_field=request.sort_field,
                sort_desc=request.sort_desc,
                limit=request.page_size,
                offset=request.offset,
            )
            return PageResult(
                rows=rows,
                total=items.count_items(search=request.search, stock=request.stock),
                page=request.page,
                page_size=request.page_size,
            )


class GetInventoryItemNamesUseCase(AuthenticatedUseCase[Collection[int], dict[int, str]]):
    """The names behind a set of item ids.

    For naming the lines on one page of a document list without loading a
    catalogue to look them up in — which is what the screens did until a
    shop had more items than the catalogue was capped at, and every line
    past that read as a dash.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: Collection[int]) -> dict[int, str]:
        with self.uow as uow:
            items = self.require(uow.inventory_items, "inventory_items")
            return items.names_by_id(request)


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