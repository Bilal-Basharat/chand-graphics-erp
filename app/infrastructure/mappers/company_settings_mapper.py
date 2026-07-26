from __future__ import annotations

from app.domain.entities.company_settings import CompanySettings
from app.infrastructure.db.models.company_settings_model import CompanySettingsModel
from app.infrastructure.mappers.base import copy_shared_fields


class CompanySettingsMapper:
    """Map between CompanySettings domain entities and ORM models."""

    @staticmethod
    def to_entity(model: CompanySettingsModel) -> CompanySettings:
        entity = CompanySettings(
            company_name=model.company_name,
            phone=model.phone,
            email=model.email,
            address=model.address,
            currency=model.currency,
            logo_path=model.logo_path,
            invoice_footer=model.invoice_footer,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: CompanySettings) -> CompanySettingsModel:
        model = CompanySettingsModel(
            company_name=entity.company_name,
            phone=entity.phone,
            email=entity.email,
            address=entity.address,
            currency=entity.currency,
            logo_path=entity.logo_path,
            invoice_footer=entity.invoice_footer,
        )
        copy_shared_fields(entity, model)
        return model