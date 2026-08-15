"""What the build does with the mail account it was given, or wasn't.

The failure this guards against is a release that packages cleanly and
ships with a dead "Forgot password" — which is exactly how the feature
reached customers before the bundle existed. Half-given credentials are
a typo, not a decision, and must stop the build.
"""
from __future__ import annotations

import pytest

from app.config import provisioning
from app.config.provisioning import SECRETS_SECTION, load_provisioning, provisioned_secret
from scripts import provision_build
from scripts.provision_build import ALLOW_UNPROVISIONED, build_bundle, write_provisioning

_COMPLETE = {
    "BUILD_SMTP_HOST": "smtp.vendor.example",
    "BUILD_SMTP_USERNAME": "noreply@vendor.example",
    "BUILD_SMTP_PASSWORD": "an-app-password",
}


@pytest.fixture(autouse=True)
def no_build_env_file(tmp_path, monkeypatch):
    """Whatever the person running the tests keeps in `.env.build` is
    theirs, and must not decide what these assert."""
    monkeypatch.setattr(provision_build, "BUILD_ENV_FILE", tmp_path / "absent.env.build")
    for name in (*_COMPLETE, "BUILD_SMTP_PORT", "BUILD_SMTP_FROM", "BUILD_SMTP_USE_TLS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(ALLOW_UNPROVISIONED, raising=False)


def _given(monkeypatch, values: dict[str, str]) -> None:
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_a_build_with_no_mail_account_is_refused(monkeypatch):
    with pytest.raises(ValueError, match="No mail account"):
        build_bundle()


def test_a_build_with_half_a_mail_account_names_what_is_missing(monkeypatch):
    _given(monkeypatch, {"BUILD_SMTP_HOST": "smtp.vendor.example"})

    with pytest.raises(ValueError, match="BUILD_SMTP_PASSWORD"):
        build_bundle()


def test_going_without_has_to_be_said_out_loud(monkeypatch):
    monkeypatch.setenv(ALLOW_UNPROVISIONED, "1")

    assert build_bundle() is None


def test_the_defaults_are_what_most_providers_want(monkeypatch):
    _given(monkeypatch, _COMPLETE)

    bundle = build_bundle()

    assert bundle["smtp"] == {
        "host": "smtp.vendor.example",
        "port": 587,
        "username": "noreply@vendor.example",
        # Most providers refuse a From that is not the account signed in as.
        "from": "noreply@vendor.example",
        "use_tls": True,
    }
    assert bundle[SECRETS_SECTION] == {"smtp-password": "an-app-password"}


def test_a_port_that_is_not_a_number_stops_the_build(monkeypatch):
    _given(monkeypatch, {**_COMPLETE, "BUILD_SMTP_PORT": "five eight seven"})

    with pytest.raises(ValueError, match="must be a number"):
        build_bundle()


def test_values_come_from_the_build_env_file_when_the_environment_is_bare(
    tmp_path, monkeypatch
):
    build_env = tmp_path / ".env.build"
    build_env.write_text(
        "# the vendor's mail account\n"
        "BUILD_SMTP_HOST=smtp.vendor.example\n"
        'BUILD_SMTP_USERNAME="noreply@vendor.example"\n'
        "BUILD_SMTP_PASSWORD=an-app-password\n"
        "BUILD_SMTP_PORT=465\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(provision_build, "BUILD_ENV_FILE", build_env)

    bundle = build_bundle()

    assert bundle["smtp"]["host"] == "smtp.vendor.example"
    assert bundle["smtp"]["username"] == "noreply@vendor.example"
    assert bundle["smtp"]["port"] == 465


def test_the_environment_wins_over_the_file(tmp_path, monkeypatch):
    """So a build machine can inject credentials without writing one."""
    build_env = tmp_path / ".env.build"
    build_env.write_text("BUILD_SMTP_HOST=smtp.from-the-file\n", encoding="utf-8")
    monkeypatch.setattr(provision_build, "BUILD_ENV_FILE", build_env)
    _given(monkeypatch, _COMPLETE)

    assert build_bundle()["smtp"]["host"] == "smtp.vendor.example"


def test_what_the_build_writes_is_what_the_application_reads(tmp_path, monkeypatch):
    """The one test that spans both halves: if the format ever drifts,
    this is what fails instead of a customer's installer."""
    _given(monkeypatch, _COMPLETE)
    path = tmp_path / "provisioning.dat"

    assert write_provisioning(path) == path

    monkeypatch.setattr(provisioning, "PROVISIONING_PATH", path)
    provisioning.reset_cache()
    try:
        assert load_provisioning()["smtp"]["host"] == "smtp.vendor.example"
        assert provisioned_secret("smtp-password") == "an-app-password"
    finally:
        provisioning.reset_cache()


def test_an_unprovisioned_build_removes_an_earlier_bundle(tmp_path, monkeypatch):
    """Otherwise the build packages credentials from a run nobody
    remembers making, and looks provisioned while doing it."""
    _given(monkeypatch, _COMPLETE)
    path = tmp_path / "provisioning.dat"
    write_provisioning(path)

    for name in _COMPLETE:
        monkeypatch.delenv(name)
    monkeypatch.setenv(ALLOW_UNPROVISIONED, "1")

    assert write_provisioning(path) is None
    assert not path.exists()
