"""What happens to text that is not a licence key.

A key arrives by whatever route a shop can manage — pasted out of an
email, half-copied, retyped by hand, saved into a file with a stray byte.
None of that may reach a screen as a traceback, and none of it may be
mistaken for a valid licence.
"""
from __future__ import annotations

import base64
import json

import pytest

from app.domain.licensing.errors import InvalidLicenseError
from app.domain.licensing.status import LicenseStatus
from app.infrastructure.licensing.license_key import (
    decode_license_key,
    entitlement_from_payload,
)

from ._helpers import Issuer


@pytest.fixture()
def issuer() -> Issuer:
    return Issuer()


def _payload_of(license_key: str) -> dict:
    return decode_license_key(license_key).payload


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "not a licence key at all",
        "CGERP1.only-two-parts",
        "CGERP1.a.b.c",
        # A key from some other product's format.
        "OTHER1.eyJhIjoxfQ.c2ln",
    ],
    ids=[
        "empty",
        "blank",
        "prose",
        "too few parts",
        "too many parts",
        "wrong format prefix",
    ],
)
def test_text_that_is_not_a_licence_key_is_refused(text: str) -> None:
    with pytest.raises(InvalidLicenseError):
        decode_license_key(text)


def test_a_key_whose_payload_is_not_base64_is_refused() -> None:
    with pytest.raises(InvalidLicenseError):
        decode_license_key("CGERP1.not!base64!.c2ln")


def test_a_key_whose_payload_is_not_json_is_refused() -> None:
    payload = base64.urlsafe_b64encode(b"this is not json").decode().rstrip("=")
    with pytest.raises(InvalidLicenseError):
        decode_license_key(f"CGERP1.{payload}.c2ln")


def test_a_key_whose_payload_is_json_but_not_an_object_is_refused() -> None:
    payload = base64.urlsafe_b64encode(b"[1, 2, 3]").decode().rstrip("=")
    with pytest.raises(InvalidLicenseError):
        decode_license_key(f"CGERP1.{payload}.c2ln")


def test_a_truncated_key_is_refused(issuer: Issuer) -> None:
    license_key = issuer.issue()
    with pytest.raises(InvalidLicenseError):
        decode_license_key(license_key[: len(license_key) // 2])


def test_a_key_broken_across_lines_by_an_email_client_still_reads(issuer: Issuer) -> None:
    license_key = issuer.issue()
    wrapped = "\n  ".join(license_key[index : index + 40] for index in range(0, len(license_key), 40))

    assert decode_license_key(wrapped).payload == decode_license_key(license_key).payload


@pytest.mark.parametrize("field", ["license_id", "key_id", "product_code", "status", "issued_at"])
def test_a_payload_missing_a_required_field_is_refused(issuer: Issuer, field: str) -> None:
    payload = issuer.payload()
    del payload[field]

    with pytest.raises(InvalidLicenseError):
        entitlement_from_payload(_payload_of(issuer.sign(payload)))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_devices", "two"),
        # bool is an int in Python, and `true` is not a device limit.
        ("max_devices", True),
        ("grace_days", 1.5),
        ("features", "reports"),
        ("features", [1, 2]),
        ("issued_at", "the first of never"),
        ("expires_at", "2027-13-45"),
        ("status", "PENDING"),
        ("customer_name", 7),
    ],
)
def test_a_payload_field_of_the_wrong_shape_is_refused(issuer: Issuer, field: str, value) -> None:
    payload = issuer.payload(**{field: value})

    with pytest.raises(InvalidLicenseError):
        entitlement_from_payload(_payload_of(issuer.sign(payload)))


@pytest.mark.parametrize("status", ["EXPIRING_SOON", "EXPIRED", "NOT_ACTIVATED", "INVALID"])
def test_a_status_only_this_app_may_conclude_cannot_be_claimed_by_a_key(
    issuer: Issuer, status: str
) -> None:
    """A key may say it is active, suspended or revoked. "Not expired" is
    not a claim it gets to make about itself."""
    payload = issuer.payload(status=status)

    with pytest.raises(InvalidLicenseError):
        entitlement_from_payload(_payload_of(issuer.sign(payload)))


@pytest.mark.parametrize("max_devices", [0, -1])
def test_a_device_limit_below_one_is_refused(issuer: Issuer, max_devices: int) -> None:
    payload = issuer.payload(max_devices=max_devices)

    with pytest.raises(InvalidLicenseError):
        entitlement_from_payload(_payload_of(issuer.sign(payload)))


def test_a_well_formed_payload_reads_into_an_entitlement(issuer: Issuer) -> None:
    entitlement = entitlement_from_payload(_payload_of(issuer.issue()))

    assert entitlement.license_id == "LIC-TEST-0001"
    assert entitlement.issued_status is LicenseStatus.ACTIVE
    assert entitlement.features == frozenset({"reports"})
    assert entitlement.max_devices == 1
    assert not entitlement.is_perpetual


def test_a_licence_with_no_expiry_is_perpetual(issuer: Issuer) -> None:
    entitlement = entitlement_from_payload(_payload_of(issuer.issue(expires_at=None)))

    assert entitlement.is_perpetual


def test_an_offset_timestamp_is_read_into_the_apps_own_clock(issuer: Issuer) -> None:
    """PKT is UTC+5, and the app compares against naive local time. An
    instant written in UTC must land five hours later, not five hours
    wrong."""
    entitlement = entitlement_from_payload(
        _payload_of(issuer.issue(expires_at="2027-01-01T00:00:00+00:00"))
    )

    assert entitlement.expires_at is not None
    assert entitlement.expires_at.hour == 5
    assert entitlement.expires_at.tzinfo is None


def test_the_signature_covers_the_payload_bytes_that_travel(issuer: Issuer) -> None:
    """Not a re-serialisation of them. Two JSON documents can mean the
    same thing and hash differently, and a scheme that signs one and
    verifies the other quietly stops rejecting anything."""
    license_key = issuer.issue()
    decoded = decode_license_key(license_key)

    assert json.loads(decoded.signed_bytes) == decoded.payload
