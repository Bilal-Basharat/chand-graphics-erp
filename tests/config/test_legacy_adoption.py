"""Carrying an existing installation into the new folder layout.

Builds before this one kept the database at the top of the application
data folder; this one keeps it in `data/` beneath. That folder is
therefore its own parent's child, which is exactly the case a
whole-directory copy gets wrong — and the case every shop in the field
will go through exactly once.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import constants, paths
from app.infrastructure.db import upgrade

HISTORICAL_NAME = "erp.db"
"""What every build so far has called the database. Written out rather
than taken from the constant, because the point of these tests is what
happens to a file already on a customer's disk under the old name."""


@pytest.fixture()
def installation(tmp_path: Path, monkeypatch):
    """An old flat layout, with this build's `data/` folder beneath it."""
    root = tmp_path / "ChandGraphicsERP"
    data = root / "data"
    data.mkdir(parents=True)

    (root / HISTORICAL_NAME).write_text("a fortnight of trading", encoding="utf-8")
    (root / "license.json").write_text('{"license_key": "CGERP1.x.y"}', encoding="utf-8")
    (root / "installation.json").write_text('{"installation_id": "abc"}', encoding="utf-8")
    (root / "session.json").write_text("{}", encoding="utf-8")
    (root / "erp.v4.backup").write_text("older still", encoding="utf-8")
    (root / "ui").mkdir()
    (root / "ui" / "checkbox-tick.png").write_bytes(b"PNG")

    monkeypatch.setattr(upgrade, "DATA_DIR", data)
    monkeypatch.setattr(upgrade, "DATABASE_PATH", data / constants.DATABASE_FILENAME)
    monkeypatch.setattr(upgrade, "legacy_data_dirs", lambda: (root,))
    return root


def test_the_database_is_carried_into_the_new_folder(installation: Path) -> None:
    upgrade.adopt_previous_installation()

    assert (installation / "data" / constants.DATABASE_FILENAME).read_text(
        encoding="utf-8"
    ) == (
        "a fortnight of trading"
    )


def test_the_licence_travels_with_the_database(installation: Path) -> None:
    """Without this, every shop meets the activation dialog the first
    time they open the build that moved the folder."""
    upgrade.adopt_previous_installation()

    assert (installation / "data" / "license.json").exists()
    assert (installation / "data" / "installation.json").exists()


def test_the_old_folder_is_not_nested_inside_itself(installation: Path) -> None:
    """The parent is one of the folders checked, so a whole-tree copy
    would walk into the destination while creating it."""
    upgrade.adopt_previous_installation()

    assert not (installation / "data" / "data").exists()
    assert not (installation / "data" / "ui").exists()


def test_the_original_is_left_where_it_was(installation: Path) -> None:
    """Copied, not moved: if anything about this build goes wrong, the
    customer's data is still sitting where it always was."""
    upgrade.adopt_previous_installation()

    assert (installation / HISTORICAL_NAME).exists()


def test_generated_assets_and_old_backups_are_left_behind(installation: Path) -> None:
    upgrade.adopt_previous_installation()

    assert not (installation / "data" / "erp.v4.backup").exists()


def test_an_installation_that_already_has_a_database_is_never_touched(
    installation: Path,
) -> None:
    live = installation / "data" / constants.DATABASE_FILENAME
    live.write_text("this build's own trading", encoding="utf-8")

    upgrade.adopt_previous_installation()

    assert live.read_text(encoding="utf-8") == "this build's own trading"


def test_a_database_named_by_an_earlier_build_is_still_adopted(
    installation: Path, monkeypatch
) -> None:
    """A future build that renames the database must still find the file
    a shop has been trading on, and take it over under the new name.

    Simulated by renaming it here rather than by waiting for that build:
    `LEGACY_DATABASE_FILENAMES` is what makes this work, and it is worth
    knowing it works before the rename, not after.
    """
    data = installation / "data"
    renamed = "erp.sqlite3"
    monkeypatch.setattr(paths, "DATABASE_FILENAMES", (renamed, HISTORICAL_NAME))
    monkeypatch.setattr(upgrade, "DATABASE_PATH", data / renamed)

    upgrade.adopt_previous_installation()

    assert (data / renamed).read_text(encoding="utf-8") == "a fortnight of trading"
    assert not (data / HISTORICAL_NAME).exists(), "adopted under the old name"
    assert (data / "license.json").exists(), "the licence still travels with it"


def test_the_current_name_is_preferred_over_an_older_one(
    installation: Path, monkeypatch
) -> None:
    """A folder holding both is a half-finished rename. The newer file is
    the one that has been traded on."""
    data = installation / "data"
    renamed = "erp.sqlite3"
    (installation / renamed).write_text("this month's trading", encoding="utf-8")
    monkeypatch.setattr(paths, "DATABASE_FILENAMES", (renamed, HISTORICAL_NAME))
    monkeypatch.setattr(upgrade, "DATABASE_PATH", data / renamed)

    upgrade.adopt_previous_installation()

    assert (data / renamed).read_text(encoding="utf-8") == "this month's trading"


def test_a_fresh_machine_with_nothing_to_adopt_is_fine(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(upgrade, "DATA_DIR", data)
    monkeypatch.setattr(upgrade, "DATABASE_PATH", data / constants.DATABASE_FILENAME)
    monkeypatch.setattr(upgrade, "legacy_data_dirs", lambda: (tmp_path / "nowhere",))

    upgrade.adopt_previous_installation()

    assert not (data / constants.DATABASE_FILENAME).exists()
