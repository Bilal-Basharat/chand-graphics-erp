"""
The two catalogues a job order points at: what the shop makes, and the
kinds of work it charges itself for.

Both are the same record — a unique name and a description — and both are
refused a delete while a job still names them, because a job that could
no longer say what it made or what work went into it would be a worse
record than one holding an unused row.
"""
from __future__ import annotations

from app.application.auth.permissions import Permission
from app.application.auth.session import CurrentUserSession
from app.application.dto.commands import (
    CreateLabourChargeTypeCommand,
    CreateProductTypeCommand,
    UpdateLabourChargeTypeCommand,
    UpdateProductTypeCommand,
)
from app.application.dto.queries import SearchQuery
from app.application.exceptions import DuplicateEntityError, NotFoundError
from app.application.use_cases.authenticated_base import AuthenticatedUseCase
from app.application.use_cases.authorized_base import AuthorizedUnitOfWorkUseCase
from app.application.use_cases.deletion_guard import ensure_not_in_use
from app.domain.entities.labour_charge_type import LabourChargeType
from app.domain.entities.product_type import ProductType


############################################################
##################### Product Types ########################
############################################################


class CreateProductTypeUseCase(AuthorizedUnitOfWorkUseCase[CreateProductTypeCommand, ProductType]):
    def execute(self, request: CreateProductTypeCommand) -> ProductType:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            product_types = self.require(uow.product_types, "product_types")

            entity = ProductType(
                name=request.name,
                description=request.description,
                created_by_user_id=current_user_id,
            )
            if product_types.get_by_name(entity.name) is not None:
                raise DuplicateEntityError(f"Product type '{entity.name}' already exists")
            return product_types.add(entity)


class UpdateProductTypeUseCase(AuthorizedUnitOfWorkUseCase[UpdateProductTypeCommand, ProductType]):
    def execute(self, request: UpdateProductTypeCommand) -> ProductType:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            product_types = self.require(uow.product_types, "product_types")

            entity = product_types.get_by_id(request.id)
            if entity is None:
                raise NotFoundError(f"Product type id={request.id} not found")

            name = request.name.strip()
            clash = product_types.get_by_name(name)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Product type '{name}' already exists")

            entity.name = name
            entity.description = request.description

            entity.updated_by_user_id = current_user_id
            return product_types.update(entity)


class DeleteProductTypeUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            product_types = self.require(uow.product_types, "product_types")
            jobs = self.require(uow.jobs, "jobs")

            entity = product_types.get_by_id(request)
            if entity is None:
                raise NotFoundError(f"Product type id={request} not found")

            ensure_not_in_use(entity.name, {"job": jobs.count_by_product_type(request)})
            product_types.delete(request)


class ListProductTypesUseCase(AuthenticatedUseCase[int, list[ProductType]]):
    def __init__(self, uow, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[ProductType]:
        with self.uow as uow:
            return self.require(uow.product_types, "product_types").list(limit=request)


class SearchProductTypesUseCase(AuthenticatedUseCase[SearchQuery, list[ProductType]]):
    def __init__(self, uow, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: SearchQuery) -> list[ProductType]:
        with self.uow as uow:
            product_types = self.require(uow.product_types, "product_types")
            if not request.term.strip():
                return product_types.list(limit=request.limit)
            return product_types.search_by_term(request.term, request.limit)


############################################################
################## Labour Charge Types #####################
############################################################


class CreateLabourChargeTypeUseCase(
    AuthorizedUnitOfWorkUseCase[CreateLabourChargeTypeCommand, LabourChargeType]
):
    def execute(self, request: CreateLabourChargeTypeCommand) -> LabourChargeType:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            types = self.require(uow.labour_charge_types, "labour_charge_types")

            entity = LabourChargeType(
                name=request.name,
                description=request.description,
                created_by_user_id=current_user_id,
            )
            if types.get_by_name(entity.name) is not None:
                raise DuplicateEntityError(f"Labour charge '{entity.name}' already exists")
            return types.add(entity)


class UpdateLabourChargeTypeUseCase(
    AuthorizedUnitOfWorkUseCase[UpdateLabourChargeTypeCommand, LabourChargeType]
):
    def execute(self, request: UpdateLabourChargeTypeCommand) -> LabourChargeType:
        self.require_permission(Permission.MANAGE_MASTER_DATA)
        current_user_id = self.current_user_id()

        with self.uow as uow:
            types = self.require(uow.labour_charge_types, "labour_charge_types")

            entity = types.get_by_id(request.id)
            if entity is None:
                raise NotFoundError(f"Labour charge type id={request.id} not found")

            name = request.name.strip()
            clash = types.get_by_name(name)
            if clash is not None and clash.id != request.id:
                raise DuplicateEntityError(f"Labour charge '{name}' already exists")

            entity.name = name
            entity.description = request.description

            entity.updated_by_user_id = current_user_id
            return types.update(entity)


class DeleteLabourChargeTypeUseCase(AuthorizedUnitOfWorkUseCase[int, None]):
    def execute(self, request: int) -> None:
        self.require_permission(Permission.MANAGE_MASTER_DATA)

        with self.uow as uow:
            types = self.require(uow.labour_charge_types, "labour_charge_types")
            jobs = self.require(uow.jobs, "jobs")

            entity = types.get_by_id(request)
            if entity is None:
                raise NotFoundError(f"Labour charge type id={request} not found")

            ensure_not_in_use(entity.name, {"job": jobs.count_by_labour_charge_type(request)})
            types.delete(request)


class ListLabourChargeTypesUseCase(AuthenticatedUseCase[int, list[LabourChargeType]]):
    def __init__(self, uow, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: int = 100) -> list[LabourChargeType]:
        with self.uow as uow:
            return self.require(uow.labour_charge_types, "labour_charge_types").list(limit=request)


class SearchLabourChargeTypesUseCase(AuthenticatedUseCase[SearchQuery, list[LabourChargeType]]):
    def __init__(self, uow, current_user_session: CurrentUserSession | None = None) -> None:
        super().__init__(current_user_session)
        self.uow = uow

    def execute(self, request: SearchQuery) -> list[LabourChargeType]:
        with self.uow as uow:
            types = self.require(uow.labour_charge_types, "labour_charge_types")
            if not request.term.strip():
                return types.list(limit=request.limit)
            return types.search_by_term(request.term, request.limit)
