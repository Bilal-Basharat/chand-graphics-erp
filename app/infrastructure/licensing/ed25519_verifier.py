"""Ed25519 signature verification, the only cryptography in the client.

Ed25519 because it has no parameters to choose badly: one curve, one hash,
32-byte keys, 64-byte signatures, and a verify that is either right or
raises. The alternative — RSA with a padding mode and a digest to pick —
offers three more ways to be subtly wrong for no benefit here.
"""
from __future__ import annotations

import base64
import binascii
import logging
from dataclasses import dataclass, field
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.domain.licensing.ports import LicenseSignatureVerifier

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Ed25519SignatureVerifier(LicenseSignatureVerifier):
    """Verifies against a fixed map of trusted public keys."""

    public_keys: Mapping[str, str]
    _loaded: dict[str, Ed25519PublicKey] = field(default_factory=dict, init=False)

    def verify(self, message: bytes, signature: bytes, key_id: str) -> bool:
        public_key = self._public_key(key_id)
        if public_key is None:
            return False
        try:
            public_key.verify(signature, message)
        except InvalidSignature:
            return False
        return True

    def _public_key(self, key_id: str) -> Ed25519PublicKey | None:
        """The trusted key for `key_id`, loaded once.

        A key_id nobody published, or a published key that is malformed,
        is a verification failure rather than a crash: an unsigned build
        must refuse licences, not fail to start.
        """
        if key_id in self._loaded:
            return self._loaded[key_id]

        encoded = self.public_keys.get(key_id)
        if encoded is None:
            return None

        try:
            public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded, validate=True))
        except (binascii.Error, ValueError):
            logger.error("Licence public key '%s' is not a valid Ed25519 key", key_id)
            return None

        self._loaded[key_id] = public_key
        return public_key
