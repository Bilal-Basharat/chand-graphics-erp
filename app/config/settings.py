from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "erp.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

SESSION_FILE_PATH = DATA_DIR / "session.json"


def _required(name: str) -> str:
    """
    Read a required environment variable.

    Raises:
        RuntimeError:
            If the environment variable does not exist.
    """
    value = os.getenv(name)

    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Missing required environment variable '{name}'."
        )

    return value.strip()


def _optional_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"Environment variable '{name}' must be an integer.") from exc
    if parsed <= 0:
        raise RuntimeError(f"Environment variable '{name}' must be greater than zero.")
    return parsed


@dataclass(slots=True, frozen=True)
class AppSettings:
    """
    Immutable application configuration.

    Values are loaded once during startup.
    """
    app_name: str
    company_name: str
    app_version: str

    initial_admin_email: str
    initial_admin_password: str
    initial_admin_full_name: str
    initial_admin_role: str

    max_login_attempts: int
    login_lockout_minutes: int

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            app_name=_required("APP_NAME"),
            company_name=_required("COMPANY_NAME"),
            app_version=_required("APP_VERSION"),

            initial_admin_email=_required("INITIAL_ADMIN_EMAIL"),
            initial_admin_password=_required("INITIAL_ADMIN_PASSWORD"),
            initial_admin_full_name=_required("INITIAL_ADMIN_FULL_NAME"),
            initial_admin_role=_required("INITIAL_ADMIN_ROLE"),

            max_login_attempts=_optional_int("MAX_LOGIN_ATTEMPTS", 5),
            login_lockout_minutes=_optional_int("LOGIN_LOCKOUT_MINUTES", 15),
        )

    def _required(name: str) -> str:
        """
        Read a required environment variable.

        Raises:
            RuntimeError:
                If the environment variable does not exist.
        """
        value = os.getenv(name)
        if value is None or value.strip() == "":
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value.strip()