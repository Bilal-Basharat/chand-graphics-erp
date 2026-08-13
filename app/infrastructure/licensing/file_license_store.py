from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.domain.licensing.activation import LicenseActivation
from app.domain.licensing.ports import LicenseStore


@dataclass(slots=True)
class FileLicenseStore(LicenseStore):
    """Keeps the activation record in a small JSON file beside the
    database, never inside it.

    Deliberately not encrypted or hidden. Nothing here is a secret: the
    key is already in the customer's hands, and what stops it being
    edited is the signature over it, not where it is kept.
    """

    license_file_path: Path

    def load(self) -> LicenseActivation | None:
        if not self.license_file_path.exists():
            return None

        try:
            data = json.loads(self.license_file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        license_key = data.get("license_key")
        installation_id = data.get("installation_id")
        if not isinstance(license_key, str) or not isinstance(installation_id, str):
            return None

        activated_at = _parse_datetime(data.get("activated_at"))
        if activated_at is None:
            return None

        return LicenseActivation(
            license_key=license_key,
            installation_id=installation_id,
            activated_at=activated_at,
        )

    def save(self, activation: LicenseActivation) -> None:
        self.license_file_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "license_key": activation.license_key,
            "installation_id": activation.installation_id,
            "activated_at": activation.activated_at.isoformat(),
        }
        temp_path = self.license_file_path.with_suffix(self.license_file_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.license_file_path)

    def clear(self) -> None:
        try:
            if self.license_file_path.exists():
                self.license_file_path.unlink()
        except OSError:
            pass


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
