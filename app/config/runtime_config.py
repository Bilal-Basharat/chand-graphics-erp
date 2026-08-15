"""
The customer's own configuration file, read at startup.

A packaged build ships no `.env` — a file beside the executable is a file
the next upgrade replaces, and a developer's own settings are not a
customer's. What genuinely varies per installation goes in
`config/settings.json` instead, written by whoever sets the machine up:

    {
      "smtp": {
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "shop@example.com",
        "from": "shop@example.com",
        "use_tls": true
      }
    }

Optional in every part. A build already knows a mail server to send from
(`app/config/provisioning.py`), so this file exists for the shop that has
one of its own and wants this installation to use it instead — a block
here overrides the build's answer for that key and leaves the rest alone.

Nothing in it is a secret: a mail password that belongs to a machine goes
to the OS credential vault, never into this file.

Nothing here raises. A configuration file that has been hand-edited into
invalid JSON is a bad afternoon for whoever edited it, not a reason a
shop cannot invoice — the application says so in the log and carries on
with its defaults.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.config.paths import RUNTIME_CONFIG_PATH

logger = logging.getLogger(__name__)

_EMPTY: Mapping[str, Any] = {}


def load_runtime_config(path: Path = RUNTIME_CONFIG_PATH) -> Mapping[str, Any]:
    """Read `config/settings.json`, or an empty mapping if there isn't one."""
    if not path.exists():
        return _EMPTY

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Configuration file at %s is unreadable; using defaults", path)
        return _EMPTY

    if not isinstance(loaded, dict):
        logger.warning("Configuration file at %s is not a JSON object; using defaults", path)
        return _EMPTY

    return loaded


def section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """One named block of the configuration.

    A block that is missing, or is present as something other than an
    object, reads as empty — so callers can ask for a value without first
    proving the file has the shape they expect.
    """
    block = config.get(name)
    return block if isinstance(block, dict) else _EMPTY
