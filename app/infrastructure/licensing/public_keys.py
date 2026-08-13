"""The public halves of the vendor's licence signing keys.

Public keys only — a signing key must never exist anywhere in this
repository or in a build produced from it. Anyone holding the private key
can issue licences for every installation in the field; it lives on the
vendor's machine, off this repo, and is backed up there.

Keys are held in a map because licences carry the `key_id` they were
signed with. That is what makes rotation possible without breaking the
installations already out there: publish the new key here alongside the
old one, sign new licences with the new key, and drop the old entry once
every licence issued under it has expired.

To create the first key pair — or the next one::

    python -m scripts.licensing.keygen --out <path outside this repo>

which prints the base64 public key and the `key_id` to paste below.
"""
from __future__ import annotations

from typing import Mapping

# key_id -> base64 (standard, padded) Ed25519 public key, 32 bytes decoded.
LICENSE_PUBLIC_KEYS: Mapping[str, str] = {
    "cg-2026-01": "4EqGz68cKUEs3pvS6eULsTexEDm9KShHGSG3aJY66p8=",
}

# The key the issuing tool signs with unless told otherwise.
DEFAULT_KEY_ID = "cg-2026-01"
