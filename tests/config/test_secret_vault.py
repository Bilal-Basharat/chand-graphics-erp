"""Every secret this application keeps goes through here.

Two things matter: that it works, and that when the machine has no vault
it degrades to storing nothing rather than to storing plaintext.
"""
from __future__ import annotations

import pytest

from app.infrastructure.security import secret_vault
from app.infrastructure.security.secret_vault import SecretVault


class FakeKeyring:
    """A vault backend that works, and can be told to fail."""

    def __init__(self, *, failing: bool = False) -> None:
        self.entries: dict[tuple[str, str], str] = {}
        self._failing = failing

    def _check(self) -> None:
        if self._failing:
            raise secret_vault.KeyringError("the vault is unavailable")

    def get_password(self, service: str, key: str) -> str | None:
        self._check()
        return self.entries.get((service, key))

    def set_password(self, service: str, key: str, secret: str) -> None:
        self._check()
        self.entries[(service, key)] = secret

    def delete_password(self, service: str, key: str) -> None:
        self._check()
        if (service, key) not in self.entries:
            raise secret_vault.KeyringError("no such entry")
        del self.entries[(service, key)]


@pytest.fixture()
def fake_keyring(monkeypatch):
    backend = FakeKeyring()
    monkeypatch.setattr(secret_vault, "keyring", backend)
    monkeypatch.setattr(secret_vault, "_backend_usable", lambda: True)
    return backend


@pytest.fixture()
def no_vault(monkeypatch):
    monkeypatch.setattr(secret_vault, "_backend_usable", lambda: False)


def test_a_secret_is_stored_and_read_back(fake_keyring) -> None:
    vault = SecretVault()

    assert vault.set("smtp-password", "hunter2")

    assert vault.get("smtp-password") == "hunter2"


def test_a_secret_that_was_never_stored_reads_as_nothing(fake_keyring) -> None:
    assert SecretVault().get("smtp-password") is None


def test_a_secret_can_be_removed(fake_keyring) -> None:
    vault = SecretVault()
    vault.set("smtp-password", "hunter2")

    vault.delete("smtp-password")

    assert vault.get("smtp-password") is None


def test_removing_something_that_is_not_there_is_not_an_error(fake_keyring) -> None:
    SecretVault().delete("smtp-password")


def test_entries_are_kept_apart_by_name(fake_keyring) -> None:
    """The sign-in password is filed under an email address and the mail
    password under a name that cannot be one, so neither can overwrite
    the other."""
    vault = SecretVault()
    vault.set("owner@shop.example", "sign-in secret")
    vault.set("smtp-password", "mail secret")

    assert vault.get("owner@shop.example") == "sign-in secret"
    assert vault.get("smtp-password") == "mail secret"


# ------------------------------------------------- no vault, no plaintext


def test_a_machine_with_no_vault_reports_that_and_stores_nothing(no_vault) -> None:
    vault = SecretVault()

    assert not vault.is_available
    assert not vault.set("smtp-password", "hunter2")
    assert vault.get("smtp-password") is None


def test_a_vault_that_fails_mid_call_is_survived(monkeypatch) -> None:
    monkeypatch.setattr(secret_vault, "keyring", FakeKeyring(failing=True))
    monkeypatch.setattr(secret_vault, "_backend_usable", lambda: True)
    vault = SecretVault()

    assert not vault.set("smtp-password", "hunter2")
    assert vault.get("smtp-password") is None
    vault.delete("smtp-password")
