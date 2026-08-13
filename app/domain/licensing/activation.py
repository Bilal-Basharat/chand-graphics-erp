from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class LicenseActivation:
    """The record that this installation was activated with this key.

    Named after the licensing server's own `Activation` — the same idea,
    kept locally so an offline start has something to verify. The key is
    stored verbatim rather than the entitlement decoded out of it: the
    signature is re-checked on every read, so a licence tampered with on
    disk stops working rather than being trusted because it was trusted
    once.
    """

    license_key: str
    installation_id: str
    activated_at: datetime
