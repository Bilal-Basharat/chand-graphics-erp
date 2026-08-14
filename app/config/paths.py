"""
Where this installation keeps everything it writes.

One rule decides all of it: **nothing the customer owns is written beside
the executable.** Replacing the application folder is exactly what an
upgrade does, and `C:\\Program Files` needs administrator rights to write
to at all. A shop that has been trading for a fortnight would lose the
lot.

So a packaged build writes under the per-user application data folder,
split by what the files are for:

    %LOCALAPPDATA%\\ChandGraphicsERP\\
        data\\     the database, and the state that belongs with it
        config\\   the customer's runtime configuration
        logs\\     what the application has to say for itself

Run from source, the same three sit in the checkout, so a working copy
stays self-contained and the database sits in `<project>/data/` exactly
as it has always been.

`ERP_DATA_DIR` overrides the data folder alone — the test and seeding
escape hatch. It is read from the real environment rather than `.env`,
because these paths are resolved at import time, before any `.env` is
loaded.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from app.config.constants import (
    APP_FOLDER_NAME,
    DATABASE_FILENAME,
    LEGACY_DATABASE_FILENAMES,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

IS_FROZEN = bool(getattr(sys, "frozen", False))
"""True in a packaged build. The one thing that tells a shipped
installation apart from a developer's checkout."""


def _app_root() -> Path:
    """The folder this installation owns."""
    if not IS_FROZEN:
        return BASE_DIR

    local_app_data = os.getenv("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / ".local" / "share"
    return root / APP_FOLDER_NAME


def _data_dir(root: Path) -> Path:
    override = os.getenv("ERP_DATA_DIR")
    if override and override.strip():
        return Path(override.strip()).expanduser()
    return root / "data"


APP_ROOT = _app_root()

DATA_DIR = _data_dir(APP_ROOT)
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_DIR = APP_ROOT / "config"

LOGS_DIR = APP_ROOT / "logs"

# ---------------------------------------------------------------- data

DATABASE_PATH = DATA_DIR / DATABASE_FILENAME

DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

SESSION_FILE_PATH = DATA_DIR / "session.json"

# Non-secret sign-in preferences (the remembered email address). The
# password that pairs with it lives in the OS credential vault, never
# here — see infrastructure/security/secret_vault.py.
SIGN_IN_PREFERENCES_PATH = DATA_DIR / "sign_in.json"

# The licence this installation was activated with, and the identifier it
# was issued against. Kept beside the database rather than inside it: a
# licence must survive a schema migration and must not travel through a
# database restore. Neither file holds a secret — the signature over the
# licence is what makes it un-editable, not where it sits.
LICENSE_FILE_PATH = DATA_DIR / "license.json"

INSTALLATION_FILE_PATH = DATA_DIR / "installation.json"

# -------------------------------------------------------------- config

# The customer's own runtime configuration, written by whoever sets the
# installation up rather than shipped with the build. Optional: absent,
# the application runs on its defaults.
RUNTIME_CONFIG_PATH = CONFIG_DIR / "settings.json"

# ---------------------------------------------------------------- logs

LOG_FILE_PATH = LOGS_DIR / "erp.log"

# -------------------------------------------------------------- legacy

# Files an earlier build left at the top level of its data folder, which
# is now this installation's parent. Adopted individually — see
# `infrastructure/db/upgrade.adopt_previous_installation`. The database
# is not among them: it is looked for by every name it has ever had, and
# arrives under this build's name.
INSTALLATION_STATE_FILES = (
    SESSION_FILE_PATH.name,
    SIGN_IN_PREFERENCES_PATH.name,
    LICENSE_FILE_PATH.name,
    INSTALLATION_FILE_PATH.name,
)

# Every name a database this application wrote may be sitting under,
# this build's first. `dict.fromkeys` keeps that order while dropping the
# repeat that appears whenever the name has not changed.
DATABASE_FILENAMES = tuple(
    dict.fromkeys((DATABASE_FILENAME, *LEGACY_DATABASE_FILENAMES))
)


def previous_database(folder: Path) -> Path | None:
    """The database an earlier build left in `folder`, whatever it called it.

    Answers `None` for a folder holding no database at all, which is the
    ordinary case: most of the places checked at startup were never an
    installation.
    """
    for name in DATABASE_FILENAMES:
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def legacy_data_dirs() -> tuple[Path, ...]:
    """Where earlier builds put the database, newest arrangement first.

    Three arrangements have existed. The most recent kept everything at
    the root of the application data folder — which is now this data
    folder's *parent*, so it is checked first. Before that the folder was
    derived from the module path, which inside a bundle lands beside the
    packaged code, or beside the executable, depending on how it was
    packaged. All are checked so an existing installation is found and
    carried over rather than silently starting empty.
    """
    if not IS_FROZEN:
        return ()
    return (APP_ROOT, BASE_DIR / "data", Path(sys.executable).resolve().parent / "data")
