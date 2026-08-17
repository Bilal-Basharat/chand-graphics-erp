from __future__ import annotations

from app.application.dto.queries import MovementPageQuery, PageResult
from app.application.dto.commands import DateRangeQuery, InventoryMovementCommand
from app.application.exceptions import NotFoundError
from app.application.use_cases.stock_helpers import decrease_stock, increase_stock, load_stock_target
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.enums.movement_type import MovementType
from app.domain.uow import UnitOfWork

from app.application.auth.session import CurrentUserSession
from app.application.auth.authorization import AuthorizationService
from app.application.auth.permissions import Permission
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import AuthorizedUseCase

class RecordInventoryMovementUseCase(AuthorizedUseCase[InventoryMovementCommand, InventoryMovement]):
    """
    Handles exceptional stock changes only:
    adjustment, damage, return, transfer.

    Normal purchase/sale stock changes are stored in purchase_items/sale_items.
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

    def execute(self, request: InventoryMovementCommand) -> InventoryMovement:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        if request.quantity_change == 0:
            raise ValueError("quantity_change cannot be zero")

        if request.movement_type == MovementType.DAMAGE and request.quantity_change > 0:
            raise ValueError("DAMAGE movements can only decrease stock")

        if request.movement_type in (MovementType.DAMAGE, MovementType.ADJUSTMENT) and not (
            request.reason and request.reason.strip()
        ):
            raise ValueError(f"reason is required for {request.movement_type.value} movements")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            movements = self.require(uow.inventory_movements, "inventory_movements")
            users = self.require(uow.users, "users")

            if request.created_by_user_id is not None and users.get_by_id(request.created_by_user_id) is None:
                raise NotFoundError(f"User id={request.created_by_user_id} not found")

            if request.source_document_id is not None and request.source_document_type is not None:
                doc_type = request.source_document_type.strip().upper()
                if doc_type == "PURCHASE":
                    purchases = self.require(uow.purchases, "purchases")
                    if purchases.get_by_id(request.source_document_id) is None:
                        raise NotFoundError(f"Purchase id={request.source_document_id} not found")
                elif doc_type == "SALE":
                    sales = self.require(uow.sales, "sales")
                    if sales.get_by_id(request.source_document_id) is None:
                        raise NotFoundError(f"Sale id={request.source_document_id} not found")

            target = load_stock_target(
                uow=uow,
                item_type=request.item_type,
                inventory_item_id=request.inventory_item_id,
            )

            if request.quantity_change > 0:
                previous_stock, resulting_stock = increase_stock(
                    target.entity, request.quantity_change
                )
            else:
                previous_stock, resulting_stock = decrease_stock(
                    target.entity, abs(request.quantity_change)
                )

            target.repository.update(target.entity)

            movement = InventoryMovement(
                movement_type=request.movement_type,
                item_type=request.item_type,
                quantity=abs(request.quantity_change),
                inventory_item_id=request.inventory_item_id,
                previous_stock=previous_stock,
                resulting_stock=resulting_stock,
                source_document_type=request.source_document_type,
                source_document_id=request.source_document_id,
                reference_no=request.reference_no,
                reason=request.reason,
                note=request.note,
                created_by_user_id=current_user_id,
            )
            return movements.add(movement)


class ListInventoryMovementsBySourceDocumentUseCase(AuthenticatedUseCase[tuple[str, int], list[InventoryMovement]]):
    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: tuple[str, int]) -> list[InventoryMovement]:
        source_document_type, source_document_id = request
        with self.uow as uow:
            movements = self.require(uow.inventory_movements, "inventory_movements")
            return movements.list_by_source_document(
                source_document_type=source_document_type,
                source_document_id=source_document_id,
            )




class PageInventoryMovementsUseCase(AuthenticatedUseCase[MovementPageQuery, PageResult]):
    """One page of one item's movement history."""

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: MovementPageQuery) -> PageResult:
        with self.uow as uow:
            movements = self.require(uow.inventory_movements, "inventory_movements")
            conditions = {
                "inventory_item_id": request.inventory_item_id,
                "movement_type": request.movement_type,
                "search": request.search,
            }
            rows = movements.page_movements(
                **conditions,
                sort_field=request.sort_field,
                sort_desc=request.sort_desc,
                limit=request.page_size,
                offset=request.offset,
            )
            return PageResult(
                rows=rows,
                total=movements.count_movements(**conditions),
                page=request.page,
                page_size=request.page_size,
            )
