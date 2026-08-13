"""The one property everything else rests on: only the vendor's key counts.

If any of these fail, every other rule in the licensing layer is
decoration — a customer could simply edit the expiry date in the file.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from app.domain.licensing.errors import InvalidLicenseError
from app.domain.licensing.status import LicenseStatus

from ._helpers import NOW, Issuer, build_provider, public_key_base64, tamper


@pytest.fixture()
def issuer() -> Issuer:
    return Issuer()


def test_a_licence_signed_by_the_trusted_key_is_accepted(tmp_path: Path, issuer: Issuer) -> None:
    provider = build_provider(tmp_path, issuer)

    state = provider.activate(issuer.issue())

    assert state.status is LicenseStatus.ACTIVE
    assert state.is_usable


@pytest.mark.parametrize(
    "changes",
    [
        {"expires_at": (NOW + timedelta(days=3650)).isoformat()},
        {"max_devices": 50},
        {"features": ["reports", "everything"]},
        {"customer_name": "Somebody Else"},
        {"status": "ACTIVE", "plan_code": "ENTERPRISE"},
    ],
    ids=["extended expiry", "more devices", "extra features", "new customer", "better plan"],
)
def test_editing_a_signed_payload_breaks_the_licence(
    tmp_path: Path, issuer: Issuer, changes: dict
) -> None:
    provider = build_provider(tmp_path, issuer)
    edited = tamper(issuer.issue(), **changes)

    with pytest.raises(InvalidLicenseError):
        provider.activate(edited)


def test_a_licence_signed_by_somebody_elses_key_is_refused(tmp_path: Path) -> None:
    """The forger's key is well-formed, the signature verifies against
    it, and it is not the key this build trusts."""
    vendor = Issuer()
    forger = Issuer()
    provider = build_provider(tmp_path, vendor)

    with pytest.raises(InvalidLicenseError):
        provider.activate(forger.issue())


def test_a_licence_naming_a_key_this_build_does_not_publish_is_refused(
    tmp_path: Path, issuer: Issuer
) -> None:
    provider = build_provider(tmp_path, issuer)

    with pytest.raises(InvalidLicenseError):
        provider.activate(issuer.issue(key_id="cg-2099-99"))


def test_a_licence_signed_under_a_rotated_key_still_verifies(tmp_path: Path) -> None:
    """Rotation is publishing a second public key, not reissuing every
    licence in the field."""
    retired = Issuer()
    current = Issuer()
    published = {
        "retired-key": public_key_base64(retired.private_key),
        current.key_id: public_key_base64(current.private_key),
    }
    provider = build_provider(tmp_path, current, public_keys=published)

    assert provider.activate(retired.issue(key_id="retired-key")).is_usable
    assert provider.activate(current.issue()).is_usable


def test_a_malformed_published_key_verifies_nothing(tmp_path: Path, issuer: Issuer) -> None:
    """A build shipped with a mistyped public key must refuse licences,
    not fail to start."""
    provider = build_provider(tmp_path, issuer, public_keys={issuer.key_id: "not-a-key"})

    with pytest.raises(InvalidLicenseError):
        provider.activate(issuer.issue())


def test_a_licence_edited_on_disk_after_activation_stops_working(
    tmp_path: Path, issuer: Issuer
) -> None:
    """The signature is re-checked on every read, not trusted because it
    was trusted once."""
    provider = build_provider(tmp_path, issuer)
    license_key = issuer.issue()
    provider.activate(license_key)

    stored = provider.store.load()
    assert stored is not None
    provider.store.save(replace(stored, license_key=tamper(license_key, max_devices=99)))

    state = provider.current_state()

    assert state.status is LicenseStatus.INVALID
    assert not state.is_usable
