"""The customer's configuration file, including the states it arrives in.

It is hand-edited by whoever sets a machine up, so every way of getting
it wrong ends at the same place: the application starts on its defaults
and says so in the log.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config.runtime_config import load_runtime_config, section


def test_an_installation_with_no_configuration_file_reads_as_empty(tmp_path: Path) -> None:
    assert load_runtime_config(tmp_path / "settings.json") == {}


def test_a_configuration_file_is_read(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"smtp": {"host": "smtp.example.com"}}', encoding="utf-8")

    assert section(load_runtime_config(path), "smtp")["host"] == "smtp.example.com"


@pytest.mark.parametrize(
    "content", ["}{ not json", "", "[1, 2, 3]", '"a string"'], ids=["broken", "empty", "list", "str"]
)
def test_a_configuration_file_that_is_not_an_object_is_ignored(tmp_path: Path, content: str) -> None:
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")

    assert load_runtime_config(path) == {}


def test_a_missing_or_mistyped_block_reads_as_empty() -> None:
    assert section({}, "smtp") == {}
    assert section({"smtp": "smtp.example.com"}, "smtp") == {}
