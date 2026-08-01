from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class SearchQuery:
    term: str
    limit: int = 50


@dataclass(slots=True)
class PurchasePaymentStatus:
    purchase_id: int
    grand_total: Decimal
    paid_amount: Decimal
    balance_amount: Decimal


@dataclass(slots=True)
class SalePaymentStatus:
    sale_id: int
    grand_total: Decimal
    paid_amount: Decimal
    balance_amount: Decimal