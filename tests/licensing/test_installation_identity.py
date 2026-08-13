"""The identifier the vendor signs a licence against.

Its whole job is to be the same tomorrow as it was today. A licence is
bound to it, so an identifier that drifts is a shop locked out of
software it paid for.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.infrastructure.licensing.file_installation_identity import FileInstallationIdentity


def _identity(tmp_path: Path) -> FileInstallationIdentity:
    return FileInstallationIdentity(tmp_path / "installation.json")


def test_an_identifier_is_created_on_first_use(tmp_path: Path) -> None:
    installation_id = _identity(tmp_path).installation_id()

    assert installation_id
    assert (tmp_path / "installation.json").exists()


def test_the_same_identifier_comes_back_every_time(tmp_path: Path) -> None:
    identity = _identity(tmp_path)

    assert identity.installation_id() == identity.installation_id()


def test_the_identifier_survives_a_restart(tmp_path: Path) -> None:
    first = _identity(tmp_path).installation_id()

    assert _identity(tmp_path).installation_id() == first


def test_two_installations_get_different_identifiers(tmp_path: Path) -> None:
    first = FileInstallationIdentity(tmp_path / "shop" / "installation.json").installation_id()
    second = FileInstallationIdentity(tmp_path / "branch" / "installation.json").installation_id()

    assert first != second


def test_the_identifier_is_written_somewhere_a_person_can_read_it(tmp_path: Path) -> None:
    """The shop has to quote this down a phone line to get a licence."""
    installation_id = _identity(tmp_path).installation_id()

    stored = json.loads((tmp_path / "installation.json").read_text(encoding="utf-8"))

    assert stored == {"installation_id": installation_id}


@pytest.mark.parametrize(
    "contents",
    ["", "not json at all", "[]", "{}", '{"installation_id": ""}', '{"installation_id": 7}'],
    ids=["empty", "prose", "not an object", "no id", "blank id", "id of the wrong type"],
)
def test_an_unreadable_identity_file_is_replaced_rather_than_trusted(
    tmp_path: Path, contents: str
) -> None:
    """A new identifier means the licence bound to the old one stops
    verifying — visible, and fixable by re-issuing. Reusing a corrupt
    file quietly is not."""
    path = tmp_path / "installation.json"
    path.write_text(contents, encoding="utf-8")

    installation_id = FileInstallationIdentity(path).installation_id()

    assert installation_id
    assert json.loads(path.read_text(encoding="utf-8")) == {"installation_id": installation_id}
