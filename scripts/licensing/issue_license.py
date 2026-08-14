"""Issue a signed licence key for one installation.

    python -m scripts.licensing.issue_license \\
        --private-key C:\\keys\\chand-licensing.pem \\
        --key-id cg-2026-01 \\
        --customer "Chand Graphics" \\
        --installation-id 6f1c... \\
        --expires "13-08-2027 17:30:00" \\
        --plan STANDARD

Vendor-side only, and dev-only: this never ships in a build, exactly as
`scripts/seed` does not. The private key is read from the path given on
the command line — it is never stored in this repository, and no default
path is offered that might tempt one into it.

**When a licence ends.** `--expires` is an instant, not a day, because
that is what the app enforces: it compares the current time against
`expires_at` to the second, and grace runs from that same instant. Times
are Pakistan Standard Time (UTC+5), which is the clock the application
reads. A date on its own means the end of that day, so a licence sold
"to 13 August" covers the whole of 13 August — see `parse_expiry` for
every accepted form.

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
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config.constants import DEFAULT_PRODUCT_CODE
from app.domain.licensing.status import LicenseStatus
from app.infrastructure.licensing.license_key import encode_license_key
from app.infrastructure.licensing.public_keys import DEFAULT_KEY_ID
from app.shared.datetimes import PKT, now_pkt

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
        help=(
            "When the licence ends, in PKT: 'YYYY-MM-DD' or 'DD-MM-YYYY' for the "
            "end of that day, or either with a time — '13-08-2027 17:30:00' — for "
            "an exact instant. Omit for a perpetual licence."
        ),
    )
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
        expires_at = parse_expiry(args.expires)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
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
    _print_term(expires_at, args.grace_days)
    print()
    print(license_key)
    if not args.installation_id:
        print(
            "\nWarning: not bound to an installation. This key will work on any machine "
            "it is pasted into. Quote the customer's installation ID unless you mean that.",
            file=sys.stderr,
        )
    return 0


def _print_term(expires_at: datetime | None, grace_days: int) -> None:
    """The two instants that matter, spelled out.

    `--expires` accepts several forms and a bare date means the end of
    that day, so what was actually signed is stated rather than left to be
    worked out from the payload — and the second line is the one to check
    when issuing a short-lived licence to test expiry against.
    """
    if expires_at is None:
        print("Perpetual: this licence never expires.")
        return
    print(f"Expires:       {expires_at:%d-%m-%Y %H:%M:%S} PKT")
    print(
        f"Access ends:   {expires_at + timedelta(days=grace_days):%d-%m-%Y %H:%M:%S} PKT"
        f"  ({grace_days} grace day{'' if grace_days == 1 else 's'})"
    )


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


def parse_expiry(value: str) -> datetime | None:
    """Read `--expires` into the exact instant the licence ends.

    Accepted, all in PKT and all stored naive, as `now_pkt()` is:

        (omitted)               perpetual
        2027-08-13              2027-08-13 23:59:59
        13-08-2027              2027-08-13 23:59:59
        2027-08-13T17:30:00     as given          (ISO, with or without T)
        13-08-2027 17:30        as given          (seconds optional)
        2027-08-13T17:30+01:00  converted to PKT

    A bare date is the *end* of that day. "Expires 13 August" is sold and
    understood as covering 13 August, and midnight would quietly take a
    day off every licence issued that way. Keys already in the field are
    unaffected: each carries its own absolute timestamp in its signed
    payload, and nothing re-reads this.
    """
    text = value.strip()
    if not text:
        return None

    parsed = _from_iso(text) or _from_day_first(text)
    if parsed is None:
        raise ValueError(
            f"--expires must be a date (YYYY-MM-DD or DD-MM-YYYY), optionally "
            f"with a time — not '{value}'."
        )

    when, has_time = parsed
    if when.tzinfo is not None:
        when = when.astimezone(PKT).replace(tzinfo=None)
    # A day with no time named is that day, all of it.
    return when if has_time else when.replace(hour=23, minute=59, second=59)


def _from_iso(text: str) -> tuple[datetime, bool] | None:
    try:
        return datetime.fromisoformat(text), len(text) > 10
    except ValueError:
        return None


def _from_day_first(text: str) -> tuple[datetime, bool] | None:
    """DD-MM-YYYY, which is how a date is written here and unreadable as
    ISO — so it can never be mistaken for one."""
    for pattern, has_time in (
        ("%d-%m-%Y %H:%M:%S", True),
        ("%d-%m-%Y %H:%M", True),
        ("%d-%m-%Y", False),
    ):
        try:
            return datetime.strptime(text, pattern), has_time
        except ValueError:
            continue
    return None


if __name__ == "__main__":
    raise SystemExit(main())
