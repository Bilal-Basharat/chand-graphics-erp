from __future__ import annotations

from app.domain.entities.login_audit import LoginAudit
from app.domain.enums.login_event_type import LoginEventType
from app.infrastructure.db.models.login_audit_model import LoginAuditModel
from app.infrastructure.mappers.base import copy_shared_fields


class LoginAuditMapper:
    @staticmethod
    def to_entity(model: LoginAuditModel) -> LoginAudit:
        entity = LoginAudit(
            user_id=model.user_id,
            email=model.email,
            event_type=LoginEventType(model.event_type),
            success=model.success,
            message=model.message,
            app_version=model.app_version,
        )
        copy_shared_fields(model, entity)
        return entity

    @staticmethod
    def to_model(entity: LoginAudit) -> LoginAuditModel:
        model = LoginAuditModel(
            user_id=entity.user_id,
            email=entity.email,
            event_type=str(entity.event_type),
            success=entity.success,
            message=entity.message,
            app_version=entity.app_version,
        )
        copy_shared_fields(entity, model)
        return model