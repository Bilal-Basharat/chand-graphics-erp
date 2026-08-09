from __future__ import annotations

from app.domain.entities.job_order_entities import (
    Job,
    JobItem,
    JobLabourCharge,
    JobMaterial,
    JobPayment,
)
from app.infrastructure.db.models.job_order_models import (
    JobItemModel,
    JobLabourChargeModel,
    JobMaterialModel,
    JobModel,
    JobPaymentModel,
)
from app.infrastructure.mappers.base import copy_shared_fields


class JobMaterialMapper:
    @staticmethod
    def to_entity(model: JobMaterialModel) -> JobMaterial:
        entity = JobMaterial(
            item_type=model.item_type,
            quantity=model.quantity,
            unit_cost=model.unit_cost,
            card_id=model.card_id,
            inventory_item_id=model.inventory_item_id,
            job_item_id=model.job_item_id,
            note=model.note,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: JobMaterial) -> JobMaterialModel:
        model = JobMaterialModel(
            item_type=entity.item_type,
            quantity=entity.quantity,
            unit_cost=entity.unit_cost,
            line_cost=entity.total_cost,
            card_id=entity.card_id,
            inventory_item_id=entity.inventory_item_id,
            note=entity.note,
        )
        copy_shared_fields(entity, model)
        return model


class JobLabourChargeMapper:
    @staticmethod
    def to_entity(model: JobLabourChargeModel) -> JobLabourCharge:
        entity = JobLabourCharge(
            labour_charge_type_id=model.labour_charge_type_id,
            amount=model.amount,
            job_item_id=model.job_item_id,
            note=model.note,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: JobLabourCharge) -> JobLabourChargeModel:
        model = JobLabourChargeModel(
            labour_charge_type_id=entity.labour_charge_type_id,
            amount=entity.amount,
            note=entity.note,
        )
        copy_shared_fields(entity, model)
        return model


class JobItemMapper:
    @staticmethod
    def to_entity(model: JobItemModel) -> JobItem:
        entity = JobItem(
            product_type_id=model.product_type_id,
            quantity=model.quantity,
            unit_price=model.unit_price,
            specifications=model.specifications,
            job_id=model.job_id,
            materials=[
                JobMaterialMapper.to_entity(m) for m in getattr(model, "materials", [])
            ],
            labour_charges=[
                JobLabourChargeMapper.to_entity(c) for c in getattr(model, "labour_charges", [])
            ],
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: JobItem) -> JobItemModel:
        model = JobItemModel(
            product_type_id=entity.product_type_id,
            quantity=entity.quantity,
            unit_price=entity.unit_price,
            line_total=entity.total_amount,
            specifications=entity.specifications,
        )
        model.materials = [JobMaterialMapper.to_model(m) for m in entity.materials]
        model.labour_charges = [
            JobLabourChargeMapper.to_model(c) for c in entity.labour_charges
        ]
        copy_shared_fields(entity, model)
        return model


class JobPaymentMapper:
    @staticmethod
    def to_entity(model: JobPaymentModel) -> JobPayment:
        entity = JobPayment(
            amount=model.amount,
            payment_method_id=model.payment_method_id,
            received_by_user_id=model.received_by_user_id,
            reference_no=model.reference_no,
            note=model.note,
            job_id=model.job_id,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: JobPayment) -> JobPaymentModel:
        model = JobPaymentModel(
            amount=entity.amount,
            payment_method_id=entity.payment_method_id,
            received_by_user_id=entity.received_by_user_id,
            reference_no=entity.reference_no,
            note=entity.note,
        )
        copy_shared_fields(entity, model)
        return model


class JobMapper:
    @staticmethod
    def to_entity(model: JobModel) -> Job:
        entity = Job(
            job_no=model.job_no,
            customer_id=model.customer_id,
            status=model.status,
            promised_date=model.promised_date,
            discount_amount=model.discount_amount,
            completed_at=model.completed_at,
            delivered_at=model.delivered_at,
            cancelled_at=model.cancelled_at,
            note=model.note,
            items=[JobItemMapper.to_entity(item) for item in getattr(model, "items", [])],
            payments=[
                JobPaymentMapper.to_entity(payment) for payment in getattr(model, "payments", [])
            ],
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: Job) -> JobModel:
        model = JobModel(
            job_no=entity.job_no,
            customer_id=entity.customer_id,
            status=entity.status,
            promised_date=entity.promised_date,
            discount_amount=entity.discount_amount,
            completed_at=entity.completed_at,
            delivered_at=entity.delivered_at,
            cancelled_at=entity.cancelled_at,
            note=entity.note,
            subtotal=entity.subtotal,
            grand_total=entity.grand_total,
            balance_amount=entity.balance_amount,
        )
        model.items = [JobItemMapper.to_model(item) for item in entity.items]
        model.payments = [JobPaymentMapper.to_model(payment) for payment in entity.payments]
        copy_shared_fields(entity, model)
        return model
