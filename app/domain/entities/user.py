from dataclasses import dataclass

from app.domain.entities.base import AuditEntity


@dataclass(slots=True)
class User(AuditEntity):

    email: str
    password_hash: str
    full_name: str
    role: str = "operator"
    is_active: bool = True
    id: int | None = None