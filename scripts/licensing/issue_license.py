"""Issue a signed licence key for one installation.

    python -m scripts.licensing.issue_license \\
        --private-key C:\\keys\\chand-licensing.pem \\
        --key-id cg-2026-01 \\
        --customer "Chand Graphics" \\
        --installation-id 6f1c... \\
        --expires 2027-08-13 \\
        --plan STANDARD

Vendor-side only, and dev-only: this never ships in a build, exactly as
`scripts/seed` does not. The private key is read from the path given on
the command line — it is never stored in this repository, and no default
path is offered that might tempt one into it.

The installation id comes from the customer: it is on the activation
dialog they are looking at, and on their licence screen afterwards. Bind
every licence to it. `--installation-id` may be omitted for a site
licence that runs anywhere, which offline means "runs on as many machines
as they copy it to" — issue those knowingly.

Until the licensing server exists, keep a note of what was issued to
whom: this tool signs licences, it does not remember them.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config.settings import DEFAULT_PRODUCT_CODE
from app.domain.licensing.status import LicenseStatus
from app.infrastructure.licensing.license_key import encode_license_key
from app.infrastructure.licensing.public_keys import DEFAULT_KEY_ID
from app.shared.datetimes import now_pkt

_ISSUABLE = ("ACTIVE", "SUSPENDED", "REVOKED")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.licensing.issue_license",
        description="Sign a licence key for one installation.",
    )
    parser.add_argument("--private-key", type=Path, required=True, help="Path to the signing key (PEM).")
    parser.add_argument("--key-id", default=DEFAULT_KEY_ID, help="Which published public key verifies it.")
    parser.add_argument("--license-id", default="", help="Your reference. Defaults to a dated one.")
    parser.add_argument("--product", default=DEFAULT_PRODUCT_CODE, help="Product this licence unlocks.")
    parser.add_argument("--customer", required=True, help="Who it is issued to, for display.")
    parser.add_argument("--plan", default="STANDARD", help="Plan name, for display.")
    parser.add_argument("--status", choices=_ISSUABLE, default="ACTIVE")
    parser.add_argument(
        "--installation-id",
        default="",
        help="Bind to this installation. Omit only for a site licence that runs anywhere.",
    )
    parser.add_argument(
        "--expires",
        default="",
        help="YYYY-MM-DD, or omit for a perpetual licence.",
    )
    parser.add_argument("--max-devices", type=int, default=1, help="Devices this licence covers.")
    parser.add_argument(
        "--grace-days",
        type=int,
        default=7,
        help="Days the app keeps working after expiry. 0 for none.",
    )
    parser.add_argument(
        "--features",
        default="",
        help="Comma-separated feature names this licence includes.",
    )
    parser.add_argument("--out", type=Path, help="Write the key to a .lic file as well as printing it.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    try:
        private_key = _load_private_key(args.private_key)
        expires_at = _parse_expiry(args.expires)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.max_devices < 1:
        print("--max-devices must be at least 1.", file=sys.stderr)
        return 1
    if args.grace_days < 0:
        print("--grace-days cannot be negative.", file=sys.stderr)
        return 1

    issued_at = now_pkt().replace(microsecond=0)
    payload = {
        "license_id": args.license_id or f"LIC-{issued_at:%Y%m%d-%H%M%S}",
        "key_id": args.key_id,
        "product_code": args.product,
        "customer_name": args.customer,
        "plan_code": args.plan,
        "status": LicenseStatus(args.status).value,
        "installation_id": args.installation_id or None,
        "max_devices": args.max_devices,
        "features": [item.strip() for item in args.features.split(",") if item.strip()],
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "grace_days": args.grace_days,
    }

    # Signed over exactly these bytes, and the key carries these bytes —
    # the client never re-serialises the payload to check it.
    signed_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    license_key = encode_license_key(signed_bytes, private_key.sign(signed_bytes))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(license_key, encoding="utf-8")

    print(json.dumps(payload, indent=2))
    print()
    print(license_key)
    if not args.installation_id:
        print(
            "\nWarning: not bound to an installation. This key will work on any machine "
            "it is pasted into until the licensing server can enforce the device count.",
            file=sys.stderr,
        )
    return 0


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    try:
        loaded = serialization.load_pem_private_key(path.expanduser().read_bytes(), password=None)
    except OSError as exc:
        raise ValueError(f"Could not read the signing key at {path}: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{path} is not a usable private key: {exc}") from exc

    if not isinstance(loaded, Ed25519PrivateKey):
        raise ValueError(f"{path} is not an Ed25519 private key.")
    return loaded


def _parse_expiry(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"--expires must be YYYY-MM-DD, not '{value}'.") from exc


if __name__ == "__main__":
    raise SystemExit(main())
