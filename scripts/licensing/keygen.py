"""Create the vendor's licence signing key pair.

    python -m scripts.licensing.keygen --out C:\\keys\\chand-licensing.pem

Run once, on the vendor's own machine. The private key it writes is the
authority behind every licence ever issued for this product:

* Keep it **outside this repository** and out of any build. Anyone who
  holds it can license any installation, for free, forever.
* Back it up somewhere you will still have after a disk failure. Losing
  it means every customer needs a new key issued under a new `key_id`.
* Rotating is supported rather than dreaded: generate a new pair with a
  new `key_id`, add its public half alongside the old one in
  `app/infrastructure/licensing/public_keys.py`, and sign new licences
  with it. Installations holding licences signed by the old key keep
  working until those expire.

The public half is printed for pasting into that module. It is public in
the real sense — publishing it costs nothing.
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.licensing.keygen",
        description="Generate an Ed25519 licence signing key pair.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Where to write the private key (PEM). Choose a path outside this repository.",
    )
    parser.add_argument(
        "--key-id",
        default="",
        help="Identifier written into every licence signed with this key, e.g. cg-2026-01.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing file. Refused by default — that file may be in use.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    out: Path = args.out.expanduser()

    if out.exists() and not args.force:
        print(
            f"{out} already exists. Refusing to overwrite a signing key.\n"
            "Pass --force only if you are certain no licence depends on it.",
            file=sys.stderr,
        )
        return 1

    private_key = Ed25519PrivateKey.generate()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    # Owner-readable only where the platform honours it. Windows ignores
    # this, so the real protection there is the folder the key is put in.
    out.chmod(0o600)

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_key = base64.b64encode(public_bytes).decode("ascii")

    key_id = args.key_id or "<choose a key id, e.g. cg-2026-01>"
    print(f"Private key written to {out} — keep it off this repository and back it up.\n")
    print("Add the public half to app/infrastructure/licensing/public_keys.py:\n")
    print(f'    "{key_id}": "{public_key}",')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
