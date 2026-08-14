"""A licensing installation built to order, signed by a throwaway key.

Every test here issues its own licences with a key pair generated in
process. The vendor's real key is never involved — the tests prove that
*a* trusted key verifies and an untrusted one does not, which is the
property that matters and the only one that stays true after a rotation.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.application.licensing.manager import LicenseManager
from app.config.settings import AppSettings, SmtpSettings
from app.infrastructure.licensing.ed25519_verifier import Ed25519SignatureVerifier
from app.infrastructure.licensing.file_installation_identity import FileInstallationIdentity
from app.infrastructure.licensing.file_license_store import FileLicenseStore
from app.infrastructure.licensing.license_key import encode_license_key
from app.infrastructure.licensing.manual_provider import ManualLicenseProvider
from app.presentation.license_watch import LicenseWatcher

PRODUCT = "TEST_PRODUCT"
KEY_ID = "test-key-01"
NOW = datetime(2026, 8, 13, 9, 0, 0)
EXPIRING_SOON_DAYS = 14


@dataclass(slots=True)
class FakeClock:
    """The app's clock, under the test's control.

    One instance is shared by the provider and the watcher, exactly as the
    container shares one callable between them — so a test moving the
    clock past an expiry moves what the licence says *and* what the
    schedule thinks the time is, which is the only way the two can be
    checked against each other.
    """

    now: datetime = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> datetime:
        self.now += timedelta(**delta)
        return self.now

    def move_to(self, when: datetime) -> datetime:
        self.now = when
        return self.now


def public_key_base64(private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")


@dataclass(slots=True)
class Issuer:
    """Signs licence keys the way the vendor's own tool does."""

    private_key: Ed25519PrivateKey = field(default_factory=Ed25519PrivateKey.generate)

    @property
    def key_id(self) -> str:
        return KEY_ID

    def public_keys(self) -> dict[str, str]:
        return {KEY_ID: public_key_base64(self.private_key)}

    def payload(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "license_id": "LIC-TEST-0001",
            "key_id": KEY_ID,
            "product_code": PRODUCT,
            "customer_name": "Test Shop",
            "plan_code": "STANDARD",
            "status": "ACTIVE",
            "installation_id": None,
            "features": ["reports"],
            "issued_at": NOW.isoformat(),
            "expires_at": (NOW + timedelta(days=365)).isoformat(),
            "grace_days": 7,
        }
        payload.update(overrides)
        return payload

    def issue(self, **overrides: Any) -> str:
        return self.sign(self.payload(**overrides))

    def sign(self, payload: dict[str, Any]) -> str:
        signed_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return encode_license_key(signed_bytes, self.private_key.sign(signed_bytes))


def tamper(license_key: str, **changes: Any) -> str:
    """Edit a signed key's payload, keeping the original signature.

    What a customer with a text editor and an hour would do.
    """
    prefix, payload_b64, signature_b64 = license_key.split(".")
    payload = json.loads(_b64decode(payload_b64))
    payload.update(changes)
    edited = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return ".".join(
        (prefix, base64.urlsafe_b64encode(edited).decode("ascii").rstrip("="), signature_b64)
    )


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def build_provider(
    tmp_path: Path,
    issuer: Issuer,
    *,
    now: datetime | Callable[[], datetime] = NOW,
    product_code: str = PRODUCT,
    public_keys: dict[str, str] | None = None,
    expiring_soon_days: int = EXPIRING_SOON_DAYS,
) -> ManualLicenseProvider:
    clock = now if callable(now) else (lambda: now)
    return ManualLicenseProvider(
        store=FileLicenseStore(tmp_path / "license.json"),
        identity=FileInstallationIdentity(tmp_path / "installation.json"),
        verifier=Ed25519SignatureVerifier(
            issuer.public_keys() if public_keys is None else public_keys
        ),
        product_code=product_code,
        expiring_soon_days=expiring_soon_days,
        clock=clock,
    )


def build_settings(**overrides: Any) -> AppSettings:
    """The build's own identity, as the licence screens are handed it."""
    values: dict[str, Any] = {
        "app_name": "Test App",
        "company_name": "Test Company",
        "app_version": "9.9.9",
        "developed_by": "Test Devs",
        "developer_email": "dev@example.com",
        "developer_contact": "0300 0000000",
        "max_login_attempts": 5,
        "login_lockout_minutes": 15,
        "product_code": PRODUCT,
        "license_expiry_warning_days": EXPIRING_SOON_DAYS,
        "smtp": SmtpSettings(host="", port=587, username="", sender="", use_tls=True),
    }
    values.update(overrides)
    return AppSettings(**values)


def build_watcher(
    tmp_path: Path,
    issuer: Issuer,
    clock: FakeClock,
    *,
    expiring_soon_days: int = EXPIRING_SOON_DAYS,
) -> LicenseWatcher:
    """A watcher over a real provider, on the same clock.

    No QApplication and no event loop: the timer this arms simply never
    fires, and `check()` — which is all its `timeout` is connected to — is
    called by the test instead. What the timer would have waited for is
    asserted through `next_transition_at()`.
    """
    provider = build_provider(
        tmp_path, issuer, now=clock, expiring_soon_days=expiring_soon_days
    )
    return LicenseWatcher(
        LicenseManager(provider),
        expiring_soon_days=expiring_soon_days,
        clock=clock,
    )
