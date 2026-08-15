"""
Put the vendor's mail account into the build being packaged.

Run by `chand_graphics_erp.spec` during the PyInstaller build, so there is
no extra command to remember and no way to ship a release that skipped
this step. It can also be run by hand, which is how a developer gets a
working "Forgot password" in a source checkout::

    python -m scripts.provision_build --out provisioning.dat

Values come from the environment first, then from `.env.build` in the
repository root — already unable to be committed, by the `.env.*` rule in
`.gitignore`. The environment first so a build machine can inject them
without writing a file, `.env.build` so a person building on their own
laptop does not have to::

    BUILD_SMTP_HOST=smtp.gmail.com
    BUILD_SMTP_PORT=587
    BUILD_SMTP_USERNAME=someone@example.com
    BUILD_SMTP_PASSWORD=<the app password>
    BUILD_SMTP_FROM=someone@example.com
    BUILD_SMTP_USE_TLS=true

The `BUILD_` prefix is deliberate: the runtime reads `SMTP_*` from the
environment as a development override, and a build that quietly picked
those up would package whatever the developer happened to be testing
against.

Packaging without them **fails the build**. A release that silently ships
with no mail account looks perfect until a customer clicks "Forgot
password", which is exactly the failure this whole mechanism exists to
end. Set `ALLOW_UNPROVISIONED_BUILD=1` to mean it on purpose.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.config.constants import DEFAULT_SMTP_PORT, PROVISIONING_FILENAME
from app.config.paths import BASE_DIR
from app.config.provisioning import SECRETS_SECTION, encode_provisioning
from app.infrastructure.security.secret_vault import SMTP_PASSWORD_KEY

BUILD_ENV_FILE = BASE_DIR / ".env.build"

ALLOW_UNPROVISIONED = "ALLOW_UNPROVISIONED_BUILD"

_REQUIRED = ("BUILD_SMTP_HOST", "BUILD_SMTP_USERNAME", "BUILD_SMTP_PASSWORD")


def _from_build_env_file() -> dict[str, str]:
    """Read `.env.build`, if there is one.

    Parsed here rather than with `python-dotenv` so that this works the
    same whether it is run from a checkout or from a build machine with
    nothing but the standard library, and so it cannot load a `.env` by
    accident.
    """
    if not BUILD_ENV_FILE.exists():
        return {}

    values: dict[str, str] = {}
    for line in BUILD_ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = _unquote(value.strip())
    return values


def _unquote(value: str) -> str:
    """Drop a matching pair of surrounding quotes, and only that.

    A password is copied out of a provider's page and pasted here, so
    anything it happens to start or end with is part of it.
    """
    for quote in ('"', "'"):
        if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
            return value[1:-1]
    return value


def _value(name: str, file_values: dict[str, str]) -> str:
    return (os.getenv(name) or file_values.get(name, "")).strip()


def build_bundle() -> dict[str, object] | None:
    """The bundle to package, or `None` when this build is going without.

    Raises when the mail account is half-given — a host with no password
    is a typo, not a decision, and packaging it would produce a build
    whose "Forgot password" opens and then fails.
    """
    file_values = _from_build_env_file()
    given = {name: _value(name, file_values) for name in _REQUIRED}

    if not any(given.values()):
        if os.getenv(ALLOW_UNPROVISIONED, "").strip() in {"1", "true", "yes", "on"}:
            return None
        raise ValueError(
            "No mail account was given for this build, so 'Forgot password' "
            f"would not work in it. Set {', '.join(_REQUIRED)} in the "
            f"environment or in {BUILD_ENV_FILE.name}, or set "
            f"{ALLOW_UNPROVISIONED}=1 if that is what you want."
        )

    missing = [name for name, value in given.items() if not value]
    if missing:
        raise ValueError(
            f"This build's mail account is incomplete; missing {', '.join(missing)}."
        )

    username = given["BUILD_SMTP_USERNAME"]
    return {
        "smtp": {
            "host": given["BUILD_SMTP_HOST"],
            "port": _port(_value("BUILD_SMTP_PORT", file_values)),
            "username": username,
            # Most providers require the sender to be the account that
            # authenticated, so that is what it defaults to.
            "from": _value("BUILD_SMTP_FROM", file_values) or username,
            "use_tls": _flag(_value("BUILD_SMTP_USE_TLS", file_values), default=True),
        },
        SECRETS_SECTION: {SMTP_PASSWORD_KEY: given["BUILD_SMTP_PASSWORD"]},
    }


def _port(value: str) -> int:
    if not value:
        return DEFAULT_SMTP_PORT
    try:
        port = int(value)
    except ValueError:
        raise ValueError(f"BUILD_SMTP_PORT must be a number, not '{value}'.") from None
    if port <= 0:
        raise ValueError("BUILD_SMTP_PORT must be greater than zero.")
    return port


def _flag(value: str, *, default: bool) -> bool:
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def write_provisioning(path: Path) -> Path | None:
    """Write the bundle for the spec to package. `None` if there is none."""
    bundle = build_bundle()
    if bundle is None:
        # Leave nothing behind: a stale file from an earlier run would be
        # packaged instead, and the build would look provisioned.
        path.unlink(missing_ok=True)
        return None

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_provisioning(bundle))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=BASE_DIR / PROVISIONING_FILENAME,
        help=f"where to write the bundle (default: {PROVISIONING_FILENAME} in the checkout)",
    )
    try:
        written = write_provisioning(parser.parse_args().out)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if written is None:
        print(f"No mail account given; nothing written ({ALLOW_UNPROVISIONED} is set).")
    else:
        # Never the values: this prints in build logs.
        print(f"Wrote {written}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
