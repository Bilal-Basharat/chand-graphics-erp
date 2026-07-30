from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.application.auth.session_store import SessionStore


@dataclass(slots=True)
class FileSessionStore(SessionStore):
    """
    Stores the current user id in a small JSON file.
    """

    session_file_path: Path

    def save_user_id(self, user_id: int) -> None:
        if user_id <= 0:
            raise ValueError("user_id must be valid")

        self.session_file_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {"user_id": user_id}
        temp_path = self.session_file_path.with_suffix(self.session_file_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload), encoding="utf-8")
        temp_path.replace(self.session_file_path)

    def load_user_id(self) -> int | None:
        if not self.session_file_path.exists():
            return None

        try:
            raw = self.session_file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return None

        user_id = data.get("user_id")
        if isinstance(user_id, int) and user_id > 0:
            return user_id

        if isinstance(user_id, str) and user_id.isdigit():
            parsed = int(user_id)
            return parsed if parsed > 0 else None

        return None

    def clear(self) -> None:
        try:
            if self.session_file_path.exists():
                self.session_file_path.unlink()
        except OSError:
            pass