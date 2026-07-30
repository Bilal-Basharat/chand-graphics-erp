from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.login_audit import LoginAudit
from app.domain.enums.login_event_type import LoginEventType
from app.domain.repositories.base import Repository


class LoginAuditRepository(Repository[LoginAudit], ABC):
    @abstractmethod
    def list_recent(self, limit: int = 100, offset: int = 0) -> list[LoginAudit]:
        raise NotImplementedError

    @abstractmethod
    def list_by_user_id(self, user_id: int, limit: int = 100, offset: int = 0) -> list[LoginAudit]:
        raise NotImplementedError

    @abstractmethod
    def list_by_event_type(
        self,
        event_type: LoginEventType,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LoginAudit]:
        raise NotImplementedError

    @abstractmethod
    def count_recent_failed_sign_ins(self, email: str, since: datetime) -> int:
        raise NotImplementedError