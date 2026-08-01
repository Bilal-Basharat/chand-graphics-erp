from dataclasses import dataclass

from app.domain.entities.base import AuditEntity


@dataclass(slots=True, kw_only=True)
class CompanySettings(AuditEntity):

    company_name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    currency: str = "PKR"
    invoice_footer: str | None = None
    logo_path: str | None = None
    id: int | None = None