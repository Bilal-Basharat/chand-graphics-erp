from __future__ import annotations

from app.application.dto.commands import DateRangeQuery, InventoryMovementCommand
from app.application.exceptions import NotFoundError
from app.application.use_cases.base import UseCase
from app.application.use_cases.stock_helpers import decrease_stock, increase_stock, load_stock_target
from app.domain.entities.inventory_movement import InventoryMovement
from app.domain.uow import UnitOfWork

from app.application.auth.session import CurrentUserSession
from app.application.use_cases.authenticated_base import AuthenticatedUseCase

class RecordInventoryMovementUseCase(AuthenticatedUseCase[InventoryMovementCommand, InventoryMovement]):
    """
    Handles exceptional stock changes only:
    adjustment, damage, return, transfer.

    Normal purchase/sale stock changes are stored in purchase_items/sale_items.
    """

    def __init__(self, uow: UnitOfWork, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: InventoryMovementCommand) -> InventoryMovement:
        if request.quantity_change == 0:
            raise ValueError("quantity_change cannot be zero")

        current_user_id = self.current_user_id()

        with self.uow as uow:
            movements = self.require(uow.inventory_movements, "inventory_movements")
            # users = self.require(uow.users, "users")

            if request.created_by_user_id is not None and users.get_by_id(request.created_by_user_id) is None:
                raise NotFoundError(f"User id={request.created_by_user_id} not found")

            target = load_stock_target(
                uow=uow,
                item_type=request.item_type,
                card_id=request.card_id,
                inventory_item_id=request.inventory_item_id,
            )

            previous_stock = target.entity.current_stock

            if request.quantity_change > 0:
                target.entity.receive_stock(request.quantity_change)
            else:
                target.entity.issue_stock(abs(request.quantity_change))

            resulting_stock = target.entity.current_stock

            if request.item_type == request.item_type.CARD:
                self.require(uow.cards, "cards").update(target.entity)
            else:
                self.require(uow.inventory_items, "inventory_items").update(target.entity)

            movement = InventoryMovement(
                movement_type=request.movement_type,
                item_type=request.item_type,
                quantity=abs(request.quantity_change),
                card_id=request.card_id,
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