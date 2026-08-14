"""
The values this installation runs on, and where each of them comes from.

Three sources, in order of precedence:

1. **Environment variables** — a development convenience. `.env` in the
   checkout is loaded into the environment by `load_development_env()`
   and can override anything here. A packaged build reads no `.env`.
2. **`config/settings.json`** — the customer's own runtime configuration,
   for what genuinely varies per installation (the mail server).
3. **`app.config.constants`** — what this build is. Always present, so
   every setting has an answer and nothing is required of a customer.

Secrets appear in none of the three. The mail password is read from the
OS credential vault at the point it is used — see
`infrastructure/security/secret_vault.py`.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.config import constants
from app.config.paths import BASE_DIR, IS_FROZEN
from app.config.runtime_config import load_runtime_config, section

ENV_FILE = BASE_DIR / ".env"
"""The development `.env`, if the developer keeps one. Never shipped."""


def load_development_env() -> None:
    """Load `<project>/.env` when running from source.

    A development convenience and nothing more. A packaged build must not
    depend on a `.env`: bundling one puts the mail password inside the
    installer for anyone who unpacks it, and a copy beside the executable
    is a file the next upgrade replaces. Production reads
    `config/settings.json` and the credential vault instead.

    Frozen builds skip this outright, so a stray file left in the install
    folder cannot change how a customer's copy behaves.
    """
    if IS_FROZEN or not ENV_FILE.exists():
        return

    from dotenv import load_dotenv

    load_dotenv(ENV_FILE)


# ------------------------------------------------------------- readers


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


def _configured(config: Mapping[str, Any], key: str, default: Any) -> Any:
    """A value from the customer's configuration file, or the default.

    Typed against the default, so a `port` someone typed as a string, or
    a `use_tls` written as `"yes"`, is ignored rather than carried into
    the application as the wrong kind of thing.
    """
    value = config.get(key, default)
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, int):
        return value if isinstance(value, int) and not isinstance(value, bool) else default
    return value if isinstance(value, str) else default


# ------------------------------------------------------------ settings


@dataclass(slots=True, frozen=True)
class SmtpSettings:
    """
    Outgoing mail server, used to send password resets.

    Optional as a whole: a shop that never configures it simply has no
    password-reset button that works, and is told so plainly rather than
    meeting a crash. `is_configured` is what callers check.

    Carries no password. That is a secret, so it is read from the OS
    credential vault by whoever is about to authenticate with it, rather
    than sitting in a configuration object for the life of the process.
    """

    host: str
    port: int
    username: str
    sender: str
    use_tls: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.sender)

    @classmethod
    def load(cls, config: Mapping[str, Any] | None = None) -> "SmtpSettings":
        mail = section(config or {}, "smtp")

        host = _optional("SMTP_HOST") or _configured(mail, "host", "")
        username = _optional("SMTP_USERNAME") or _configured(mail, "username", "")

        port = _configured(mail, "port", constants.DEFAULT_SMTP_PORT)
        if port <= 0:
            port = constants.DEFAULT_SMTP_PORT

        return cls(
            host=host,
            port=_optional_int("SMTP_PORT", port),
            username=username,
            # Falls back to the account being authenticated with, which is
            # what it is for most providers.
            sender=_optional("SMTP_FROM") or _configured(mail, "from", "") or username,
            use_tls=_optional_flag("SMTP_USE_TLS", _configured(mail, "use_tls", True)),
        )


@dataclass(slots=True, frozen=True)
class AppSettings:
    """
    Immutable application configuration.

    Loaded once during startup. Every field has an answer without any
    configuration at all — a fresh installation with no `.env` and no
    `config/settings.json` starts and runs.
    """

    app_name: str
    company_name: str
    app_version: str
    developed_by: str
    developer_email: str
    developer_contact: str

    max_login_attempts: int
    login_lockout_minutes: int

    product_code: str
    license_expiry_warning_days: int

    smtp: SmtpSettings

    @classmethod
    def load(cls) -> "AppSettings":
        config = load_runtime_config()

        return cls(
            # Identity and version belong to the build, not to the
            # machine it lands on. A development checkout can still say
            # otherwise through .env.
            app_name=_optional("APP_NAME", constants.APP_NAME),
            company_name=_optional("COMPANY_NAME", constants.COMPANY_NAME),
            app_version=_optional("APP_VERSION", constants.APP_VERSION),
            developed_by=_optional("DEVELOPED_BY", constants.DEVELOPED_BY),
            developer_email=_optional("DEVELOPER_EMAIL", constants.DEVELOPER_EMAIL),
            developer_contact=_optional("DEVELOPER_CONTACT", constants.DEVELOPER_CONTACT),

            max_login_attempts=_optional_int(
                "MAX_LOGIN_ATTEMPTS", constants.DEFAULT_MAX_LOGIN_ATTEMPTS
            ),
            login_lockout_minutes=_optional_int(
                "LOGIN_LOCKOUT_MINUTES", constants.DEFAULT_LOGIN_LOCKOUT_MINUTES
            ),

            # Which product a licence must name to be accepted here. The
            # same key format will serve other products later, and this
            # is what stops one product's licence unlocking another.
            product_code=_optional("PRODUCT_CODE", constants.DEFAULT_PRODUCT_CODE),
            license_expiry_warning_days=_optional_int(
                "LICENSE_EXPIRY_WARNING_DAYS", constants.DEFAULT_LICENSE_EXPIRY_WARNING_DAYS
            ),

            smtp=SmtpSettings.load(config),
        )
