"""What a build carries, and what happens when it carries nothing usable.

The failure this guards against is a packaged build that was made wrong —
no bundle, a truncated one, or one produced before the key material
changed — taking the whole application down on the first read. It must
behave exactly as an unprovisioned build does: mail is off, nothing else
is affected.
"""
from __future__ import annotations

import pytest

from app.config import provisioning
from app.config.provisioning import (
    SECRETS_SECTION,
    encode_provisioning,
    load_provisioning,
    provisioned_secret,
)

_BUNDLE = {
    "smtp": {"host": "smtp.example.com", "port": 465, "username": "shop@example.com"},
    SECRETS_SECTION: {"smtp-password": "hunter2"},
}


@pytest.fixture()
def bundle_at(tmp_path, monkeypatch):
    """Point the module at a bundle of the test's choosing."""

    def _write(content: bytes | None) -> None:
        path = tmp_path / "provisioning.dat"
        if content is not None:
            path.write_bytes(content)
        monkeypatch.setattr(provisioning, "PROVISIONING_PATH", path)
        provisioning.reset_cache()

    yield _write
    provisioning.reset_cache()


def test_a_bundle_survives_the_round_trip(bundle_at):
    bundle_at(encode_provisioning(_BUNDLE))

    assert load_provisioning() == {"smtp": _BUNDLE["smtp"]}
    assert provisioned_secret("smtp-password") == "hunter2"


def test_the_secrets_block_is_not_part_of_the_configuration(bundle_at):
    """It is read by name, at the point of use, and never handed to
    `app.config.settings` along with everything else."""
    bundle_at(encode_provisioning(_BUNDLE))

    assert SECRETS_SECTION not in load_provisioning()


def test_a_build_with_no_bundle_simply_has_none(bundle_at):
    bundle_at(None)

    assert load_provisioning() == {}
    assert provisioned_secret("smtp-password") is None


@pytest.mark.parametrize(
    "content",
    [b"", b"not a bundle at all", encode_provisioning(_BUNDLE)[:20]],
    ids=["empty", "garbage", "truncated"],
)
def test_an_unreadable_bundle_is_ignored_rather_than_fatal(bundle_at, content):
    bundle_at(content)

    assert load_provisioning() == {}
    assert provisioned_secret("smtp-password") is None


def test_a_bundle_from_a_different_key_is_ignored(bundle_at, monkeypatch):
    """Which is what a bundle produced by an older build looks like once
    the key material has been rotated."""
    monkeypatch.setattr(provisioning, "_KEY_MATERIAL", b"some other build")
    foreign = encode_provisioning(_BUNDLE)
    monkeypatch.undo()
    bundle_at(foreign)

    assert load_provisioning() == {}


def test_a_bundle_holding_something_other_than_an_object_is_ignored(bundle_at):
    bundle_at(encode_provisioning(["not", "an", "object"]))  # type: ignore[arg-type]

    assert load_provisioning() == {}


def test_a_secret_that_was_never_stored_reads_as_missing(bundle_at):
    bundle_at(encode_provisioning({"smtp": {"host": "smtp.example.com"}}))

    assert provisioned_secret("smtp-password") is None


def test_a_blank_secret_reads_as_missing(bundle_at):
    """Otherwise it is handed to `server.login()` as a password, and the
    provider's refusal is what gets reported."""
    bundle_at(encode_provisioning({SECRETS_SECTION: {"smtp-password": ""}}))

    assert provisioned_secret("smtp-password") is None
