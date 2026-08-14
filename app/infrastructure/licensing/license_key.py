"""The licence key wire format: how an entitlement is written down.

    CGERP1.<base64url(payload json)>.<base64url(ed25519 signature)>

Three parts, dot-separated, no padding — short enough to paste into an
email or a WhatsApp message, which is how these will actually reach a
shop.

The signature is taken over the payload bytes exactly as they travel, so
verification never has to re-serialise the JSON and hope it lands on the
same bytes the signer used. That "canonical JSON" trap is how signature
schemes quietly stop rejecting anything, and avoiding it costs nothing:
decode base64, verify those bytes, only then parse.

Every failure in here raises `InvalidLicenseError` with a reason. A key
arriving from a customer's clipboard is arbitrary text, and nothing in
this module may leak a `KeyError`, a `ValueError` or a decoder's own
exception to a screen.
"""
from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.licensing.entitlement import LicenseEntitlement
from app.domain.licensing.errors import InvalidLicenseError
from app.domain.licensing.status import LicenseStatus
from app.shared.datetimes import PKT

KEY_PREFIX = "CGERP1"
_PART_COUNT = 3
_UNREADABLE = "This licence key is not readable. Please check it was copied in full."


@dataclass(frozen=True, slots=True)
class DecodedLicenseKey:
    """A key split into its parts, before anything in it is trusted."""

    key_id: str
    signed_bytes: bytes
    signature: bytes
    payload: dict[str, Any]


def encode_license_key(payload: bytes, signature: bytes) -> str:
    """Assemble a key from a signed payload. Used by the issuing tool."""
    return ".".join((KEY_PREFIX, _b64encode(payload), _b64encode(signature)))


def decode_license_key(license_key: str) -> DecodedLicenseKey:
    """Split and parse a key. Says nothing about whether it is genuine."""
    if not license_key or not license_key.strip():
        raise InvalidLicenseError("Please enter a licence key.")

    # Keys get pasted out of emails, chat messages and PDFs, all of which
    # introduce line breaks and stray spaces. None of that is the shop's
    # mistake, so none of it is treated as one.
    parts = "".join(license_key.split()).split(".")
    if len(parts) != _PART_COUNT or parts[0] != KEY_PREFIX:
        raise InvalidLicenseError(_UNREADABLE)

    signed_bytes = _b64decode(parts[1])
    signature = _b64decode(parts[2])

    try:
        payload = json.loads(signed_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidLicenseError(_UNREADABLE) from exc

    if not isinstance(payload, dict):
        raise InvalidLicenseError(_UNREADABLE)

    return DecodedLicenseKey(
        key_id=_text(payload, "key_id"),
        signed_bytes=signed_bytes,
        signature=signature,
        payload=payload,
    )


def entitlement_from_payload(payload: dict[str, Any]) -> LicenseEntitlement:
    """Read a verified payload into the domain's own type.

    Call this only after the signature has been checked — the fields are
    trusted to be well-formed here, not to be true.

    Only the fields named below are read. A payload carrying more than
    that is not an error: keys already issued in the field keep verifying,
    because the signature covers the bytes as they travel and nothing here
    re-serialises them.
    """
    try:
        return LicenseEntitlement(
            license_id=_text(payload, "license_id"),
            product_code=_text(payload, "product_code"),
            customer_name=_optional_text(payload, "customer_name"),
            plan_code=_optional_text(payload, "plan_code"),
            issued_status=_status(payload),
            installation_id=_optional_text(payload, "installation_id") or None,
            features=frozenset(_features(payload)),
            issued_at=_datetime(payload, "issued_at"),
            expires_at=_optional_datetime(payload, "expires_at"),
            # Absent means no grace, which is a licence with no
            # concession rather than a missing field.
            grace_days=_integer(payload, "grace_days", default=0),
        )
    except ValueError as exc:
        # Domain invariants (empty id, negative grace, expiry before
        # issue) reach the shop as a refusal, not a crash.
        raise InvalidLicenseError(f"This licence key is not valid: {exc}") from exc


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (binascii.Error, ValueError) as exc:
        raise InvalidLicenseError(_UNREADABLE) from exc


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InvalidLicenseError(f"This licence key is missing its {field.replace('_', ' ')}.")
    return value.strip()


def _optional_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise InvalidLicenseError(f"This licence key has an unreadable {field.replace('_', ' ')}.")
    return value.strip()


def _integer(payload: dict[str, Any], field: str, *, default: int | None = None) -> int:
    value = payload.get(field)
    if value is None and default is not None:
        return default
    # bool is an int in Python; `"grace_days": true` is not a number of days.
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidLicenseError(f"This licence key has an unreadable {field.replace('_', ' ')}.")
    return value


def _features(payload: dict[str, Any]) -> list[str]:
    value = payload.get("features")
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise InvalidLicenseError("This licence key has an unreadable feature list.")
    return [item.strip() for item in value if item.strip()]


def _status(payload: dict[str, Any]) -> LicenseStatus:
    raw = _text(payload, "status")
    try:
        return LicenseStatus(raw.upper())
    except ValueError as exc:
        raise InvalidLicenseError(f"This licence key has an unknown status ({raw}).") from exc


def _datetime(payload: dict[str, Any], field: str) -> datetime:
    return _to_local(_text(payload, field), field)


def _optional_datetime(payload: dict[str, Any], field: str) -> datetime | None:
    value = payload.get(field)
    if value is None:
        return None
    return _to_local(_text(payload, field), field)


def _to_local(value: str, field: str) -> datetime:
    """Parse an ISO-8601 timestamp into the app's clock.

    The app compares against `now_pkt()`, which is naive local time, so an
    offset-carrying timestamp is converted rather than compared across
    kinds — mixing the two raises at the comparison, hours after the
    mistake was made. A timestamp with no offset is already local.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidLicenseError(
            f"This licence key has an unreadable {field.replace('_', ' ')}."
        ) from exc

    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(PKT).replace(tzinfo=None)
