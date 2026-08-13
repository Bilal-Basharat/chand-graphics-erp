from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.domain.licensing.ports import InstallationIdentity


@dataclass(slots=True)
class FileInstallationIdentity(InstallationIdentity):
    """A random identifier written once, on first run, and kept.

    A random UUID rather than a hardware fingerprint. A fingerprint made
    from disk serials or MAC addresses looks stronger and behaves worse:
    it changes when a disk is replaced or a network adapter is disabled,
    and the shop that had a repair done is then locked out of software it
    paid for. The identifier is what the vendor signs into the key, so
    what it must be is *stable* — and a file in the data folder is stable
    in exactly the cases that matter.

    It travels with the data folder, so a shop that copies its whole
    installation to a second machine carries the licence with it. Offline,
    nothing can prevent that; the licensing server, which will see the
    same id activating twice, is what will.
    """

    installation_file_path: Path
    _installation_id: str | None = field(default=None, init=False)

    def installation_id(self) -> str:
        if self._installation_id is None:
            self._installation_id = self._read() or self._create()
        return self._installation_id

    def _read(self) -> str | None:
        if not self.installation_file_path.exists():
            return None

        try:
            data = json.loads(self.installation_file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Unreadable means a new id, and a new id means the licence
            # bound to the old one stops verifying — visible, and fixable
            # by re-issuing. Silently reusing a corrupt file is not.
            return None

        if not isinstance(data, dict):
            return None

        installation_id = data.get("installation_id")
        if isinstance(installation_id, str) and installation_id.strip():
            return installation_id.strip()
        return None

    def _create(self) -> str:
        installation_id = uuid.uuid4().hex
        self.installation_file_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {"installation_id": installation_id}
        temp_path = self.installation_file_path.with_suffix(
            self.installation_file_path.suffix + ".tmp"
        )
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.installation_file_path)
        return installation_id
