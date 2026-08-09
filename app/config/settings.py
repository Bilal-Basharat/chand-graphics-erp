from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_FOLDER_NAME = "ChandGraphicsERP"


def _resolve_env_file() -> Path:
    """The .env this installation reads its configuration from.

    Named explicitly rather than left to python-dotenv's own search, which
    falls back to the *working directory* as soon as the app is frozen.
    That is fine when it is started from its own folder and wrong the
    moment a shortcut sets the working directory elsewhere — the app then
    starts with no configuration at all and dies on the first required
    setting.

    A packaged build reads the copy bundled inside it, so there is nothing
    to lose or mis-place. A file placed beside the executable still wins,
    which is what lets one build be pointed at a different mail server or
    version without rebuilding it.
    """
    if not getattr(sys, "frozen", False):
        return BASE_DIR / ".env"

    beside_executable = Path(sys.executable).resolve().parent / ".env"
    if beside_executable.exists():
        return beside_executable

    # PyInstaller unpacks bundled data here — the _internal folder for a
    # onedir build, a temporary directory for onefile.
    return Path(getattr(sys, "_MEIPASS", BASE_DIR)) / ".env"


ENV_FILE = _resolve_env_file()


def _resolve_data_dir() -> Path:
    """Where this installation keeps the customer's database.

    Running from source it is the repository's own `data/`, so a checkout
    stays self-contained.

    Installed, it is the per-user application data folder — never beside
    the executable. Data written next to the program is data an installer
    deletes: replacing the application folder is exactly what an upgrade
    does, and a shop that has been trading for a fortnight would lose all
    of it. The folder here outlives uninstalls, and needs no
    administrator rights to write to, which `C:\\Program Files` does.
    """
    override = os.getenv("ERP_DATA_DIR")
    if override and override.strip():
        return Path(override.strip()).expanduser()

    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA")
        root = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
        return root / APP_FOLDER_NAME

    return BASE_DIR / "data"


def legacy_data_dirs() -> tuple[Path, ...]:
    """Where earlier builds put the database, newest guess first.

    Those builds derived the folder from the module path, which inside a
    bundle lands beside the packaged code — or beside the executable,
    depending on how it was packaged. Both are checked so an existing
    installation is found and carried over rather than silently starting
    empty.
    """
    if not getattr(sys, "frozen", False):
        return ()
    return (BASE_DIR / "data", Path(sys.executable).resolve().parent / "data")


DATA_DIR = _resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "erp.db"

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

SESSION_FILE_PATH = DATA_DIR / "session.json"

# Non-secret sign-in preferences (the remembered email address). The
# password that pairs with it lives in the OS credential vault, never
# here — see presentation/services/credential_store.py.
SIGN_IN_PREFERENCES_PATH = DATA_DIR / "sign_in.json"


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


def _optional(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def _optional_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
class SmtpSettings:
    """
    Outgoing mail server, used to send password resets.

    Optional as a whole: a shop that never configures it simply has no
    password-reset button that works, and is told so plainly rather than
    meeting a crash. `is_configured` is what callers check.
    """

    host: str
    port: int
    username: str
    password: str
    sender: str
    use_tls: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.sender)

    @classmethod
    def from_env(cls) -> "SmtpSettings":
        return cls(
            host=_optional("SMTP_HOST"),
            port=_optional_int("SMTP_PORT", 587),
            username=_optional("SMTP_USERNAME"),
            password=_optional("SMTP_PASSWORD"),
            # Falls back to the account being authenticated with, which is
            # what it is for most providers.
            sender=_optional("SMTP_FROM") or _optional("SMTP_USERNAME"),
            use_tls=_optional_flag("SMTP_USE_TLS", True),
        )


@dataclass(slots=True, frozen=True)
class AppSettings:
    """
    Immutable application configuration.

    Values are loaded once during startup.
    """
    app_name: str
    company_name: str
    app_version: str
    developed_by: str
    developer_email: str
    developer_contact: str

    initial_admin_email: str
    initial_admin_password: str
    initial_admin_full_name: str
    initial_admin_role: str

    max_login_attempts: int
    login_lockout_minutes: int

    smtp: SmtpSettings = field(default_factory=SmtpSettings.from_env)

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            app_name=_required("APP_NAME"),
            company_name=_required("COMPANY_NAME"),
            app_version=_required("APP_VERSION"),
            # Optional, unlike the values around it: a customer upgrading
            # keeps the .env file they were shipped, and making this
            # required would stop the new build starting at all on every
            # installation that predates it.
            developed_by=_optional("DEVELOPED_BY", "Alvi-Systems"),
            developer_email=_optional("DEVELOPER_EMAIL"),
            developer_contact=_optional("DEVELOPER_CONTACT"),

            initial_admin_email=_required("INITIAL_ADMIN_EMAIL"),
            initial_admin_password=_required("INITIAL_ADMIN_PASSWORD"),
            initial_admin_full_name=_required("INITIAL_ADMIN_FULL_NAME"),
            initial_admin_role=_required("INITIAL_ADMIN_ROLE"),

            max_login_attempts=_optional_int("MAX_LOGIN_ATTEMPTS", 5),
            login_lockout_minutes=_optional_int("LOGIN_LOCKOUT_MINUTES", 15),

            smtp=SmtpSettings.from_env(),
        )