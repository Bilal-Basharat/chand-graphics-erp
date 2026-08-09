"""
Persistence for the job order aggregate and the two catalogues it needs.

A job is only meaningful with its children loaded — the profit on it is
the difference between what was charged and what the materials and labour
cost, and neither figure exists without them. So every read that returns
jobs pulls the whole tree in one go rather than leaving the caller to
trigger a query per row.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.entities.job_order_entities import Job
from app.domain.entities.labour_charge_type import LabourChargeType
from app.domain.entities.product_type import ProductType
from app.domain.enums.item_type import ItemType
from app.domain.repositories.catalogue_repositories import (
    LabourChargeTypeRepository as LabourChargeTypeRepositoryPort,
    ProductTypeRepository as ProductTypeRepositoryPort,
)
from app.domain.repositories.job_repository import JobRepository as JobRepositoryPort
from app.infrastructure.db.models.customer_model import CustomerModel
from app.infrastructure.db.models.job_order_models import (
    JobItemModel,
    JobLabourChargeModel,
    JobMaterialModel,
    JobModel,
)
from app.infrastructure.db.models.labour_charge_type_model import LabourChargeTypeModel
from app.infrastructure.db.models.product_type_model import ProductTypeModel
from app.infrastructure.mappers.catalogue_mappers import (
    LabourChargeTypeMapper,
    ProductTypeMapper,
)
from app.infrastructure.mappers.job_order_mappers import JobMapper
from app.infrastructure.repositories.base import SQLAlchemyRepository

_FULL_TREE = (
    selectinload(JobModel.items).selectinload(JobItemModel.materials),
    selectinload(JobModel.items).selectinload(JobItemModel.labour_charges),
    selectinload(JobModel.payments),
)


def _count_jobs_holding(condition) -> object:
    return select(func.count(func.distinct(JobItemModel.job_id))).where(condition)


############################################################
###################### Job Repository ######################
############################################################
class SqlAlchemyJobRepository(SQLAlchemyRepository[Job, JobModel], JobRepositoryPort):
    def __init__(self, session: Session) -> None:
        super().__init__(session, JobModel, JobMapper)

    def get_by_id(self, entity_id: int) -> Job | None:
        stmt = select(JobModel).where(JobModel.id == entity_id).options(*_FULL_TREE)
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else JobMapper.to_entity(model)

    def get_by_job_no(self, job_no: str) -> Job | None:
        stmt = select(JobModel).where(JobModel.job_no == job_no).options(*_FULL_TREE)
        model = self.session.execute(stmt).scalar_one_or_none()
        return None if model is None else JobMapper.to_entity(model)

    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        limit: int = 200,
    ) -> list[Job]:
        stmt = (
            select(JobModel)
            .where(JobModel.created_at >= start)
            .where(JobModel.created_at <= end)
            .order_by(JobModel.created_at.desc())
            .options(*_FULL_TREE)
            .limit(limit)
        )
        return [JobMapper.to_entity(m) for m in self.session.execute(stmt).scalars().all()]

    def search_by_term(self, term: str, limit: int = 50) -> list[Job]:
        pattern = f"%{term.strip()}%"
        stmt = (
            select(JobModel)
            # Outer join: a walk-in job has no customer and still has to be
            # findable by its number.
            .outerjoin(CustomerModel, JobModel.customer_id == CustomerModel.id)
            .where(
                or_(
                    JobModel.job_no.ilike(pattern),
                    CustomerModel.name.ilike(pattern),
                    JobModel.note.ilike(pattern),
                )
            )
            .order_by(JobModel.created_at.desc())
            .options(*_FULL_TREE)
            .limit(limit)
        )
        return [JobMapper.to_entity(m) for m in self.session.execute(stmt).scalars().all()]

    def count_by_material(self, item_type: ItemType, item_id: int) -> int:
        column = (
            JobMaterialModel.card_id
            if item_type is ItemType.CARD
            else JobMaterialModel.inventory_item_id
        )
        stmt = (
            select(func.count(func.distinct(JobItemModel.job_id)))
            .select_from(JobMaterialModel)
            .join(JobItemModel, JobMaterialModel.job_item_id == JobItemModel.id)
            .where(column == item_id)
        )
        return int(self.session.execute(stmt).scalar_one())

    def count_by_product_type(self, product_type_id: int) -> int:
        stmt = _count_jobs_holding(JobItemModel.product_type_id == product_type_id)
        return int(self.session.execute(stmt).scalar_one())

    def count_by_labour_charge_type(self, labour_charge_type_id: int) -> int:
        stmt = (
            select(func.count(func.distinct(JobItemModel.job_id)))
            .select_from(JobLabourChargeModel)
            .join(JobItemModel, JobLabourChargeModel.job_item_id == JobItemModel.id)
            .where(JobLabourChargeModel.labour_charge_type_id == labour_charge_type_id)
        )
        return int(self.session.execute(stmt).scalar_one())

    def count_by_customer(self, customer_id: int) -> int:
        stmt = select(func.count(JobModel.id)).where(JobModel.customer_id == customer_id)
        return int(self.session.execute(stmt).scalar_one())


############################################################
################## Product Type Repository #################
############################################################
class SqlAlchemyProductTypeRepository(
    SQLAlchemyRepository[ProductType, ProductTypeModel],
    ProductTypeRepositoryPort,
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ProductTypeModel, ProductTypeMapper)

    def get_by_name(self, name: str) -> ProductType | None:
        return self.find_one_by("name", name)

    def list(self, limit: int = 100, offset: int = 0) -> list[ProductType]:
        stmt = (
            select(ProductTypeModel)
            .order_by(ProductTypeModel.name.asc())
            .offset(offset)
            .limit(limit)
        )
        return [ProductTypeMapper.to_entity(m) for m in self.session.execute(stmt).scalars().all()]

    def search_by_term(self, term: str, limit: int = 50) -> list[ProductType]:
        pattern = f"%{term.strip()}%"
        stmt = (
            select(ProductTypeModel)
            .where(
                or_(
                    ProductTypeModel.name.ilike(pattern),
                    ProductTypeModel.description.ilike(pattern),
                )
            )
            .order_by(ProductTypeModel.name.asc())
            .limit(limit)
        )
        return [ProductTypeMapper.to_entity(m) for m in self.session.execute(stmt).scalars().all()]


############################################################
############### Labour Charge Type Repository ##############
############################################################
class SqlAlchemyLabourChargeTypeRepository(
    SQLAlchemyRepository[LabourChargeType, LabourChargeTypeModel],
    LabourChargeTypeRepositoryPort,
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, LabourChargeTypeModel, LabourChargeTypeMapper)

    def get_by_name(self, name: str) -> LabourChargeType | None:
        return self.find_one_by("name", name)

    def list(self, limit: int = 100, offset: int = 0) -> list[LabourChargeType]:
        stmt = (
            select(LabourChargeTypeModel)
            .order_by(LabourChargeTypeModel.name.asc())
            .offset(offset)
            .limit(limit)
        )
        return [
            LabourChargeTypeMapper.to_entity(m)
            for m in self.session.execute(stmt).scalars().all()
        ]

    def search_by_term(self, term: str, limit: int = 50) -> list[LabourChargeType]:
        pattern = f"%{term.strip()}%"
        stmt = (
            select(LabourChargeTypeModel)
            .where(
                or_(
                    LabourChargeTypeModel.name.ilike(pattern),
                    LabourChargeTypeModel.description.ilike(pattern),
                )
            )
            .order_by(LabourChargeTypeModel.name.asc())
            .limit(limit)
        )
        return [
            LabourChargeTypeMapper.to_entity(m)
            for m in self.session.execute(stmt).scalars().all()
        ]
