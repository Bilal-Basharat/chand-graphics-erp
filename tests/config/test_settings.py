"""What the application runs on when nobody has configured anything.

The failure this guards against is the one the whole configuration
refactor exists for: a packaged build, on a customer's machine, with no
`.env` anywhere — which used to die on the first `_required` key before a
window ever appeared.
"""
from __future__ import annotations

import pytest

from app.config import constants
from app.config.settings import AppSettings, SmtpSettings

_ENVIRONMENT_KEYS = (
    "APP_NAME",
    "COMPANY_NAME",
    "APP_VERSION",
    "DEVELOPED_BY",
    "DEVELOPER_EMAIL",
    "DEVELOPER_CONTACT",
    "MAX_LOGIN_ATTEMPTS",
    "LOGIN_LOCKOUT_MINUTES",
    "PRODUCT_CODE",
    "LICENSE_EXPIRY_WARNING_DAYS",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_FROM",
    "SMTP_USE_TLS",
)


@pytest.fixture()
def bare_environment(monkeypatch):
    """A machine that has been told nothing — a production install."""
    for key in _ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def no_config_file(monkeypatch):
    """No config/settings.json either."""
    monkeypatch.setattr("app.config.settings.load_runtime_config", lambda: {})


@pytest.fixture(autouse=True)
def no_provisioning(monkeypatch):
    """A build packaged with no mail account.

    Automatic, because a developer who has generated a `provisioning.dat`
    in their checkout would otherwise see these tests read it and fail on
    a machine where the code is right.
    """
    monkeypatch.setattr("app.config.settings.load_provisioning", lambda: {})


# ------------------------------------------------------------ defaults


def test_the_application_loads_with_no_configuration_at_all(bare_environment, no_config_file):
    settings = AppSettings.load()

    assert settings.app_name == constants.APP_NAME
    assert settings.app_version == constants.APP_VERSION
    assert settings.company_name == constants.COMPANY_NAME
    assert settings.developed_by == constants.DEVELOPED_BY
    assert settings.product_code == constants.DEFAULT_PRODUCT_CODE
    assert settings.max_login_attempts == constants.DEFAULT_MAX_LOGIN_ATTEMPTS
    assert settings.login_lockout_minutes == constants.DEFAULT_LOGIN_LOCKOUT_MINUTES
    assert settings.license_expiry_warning_days == constants.DEFAULT_LICENSE_EXPIRY_WARNING_DAYS


def test_no_mail_server_means_the_feature_is_simply_off(bare_environment, no_config_file):
    assert not AppSettings.load().smtp.is_configured


def test_the_environment_still_wins_while_developing(bare_environment, no_config_file, monkeypatch):
    monkeypatch.setenv("APP_NAME", "Printing Press ERP")
    monkeypatch.setenv("PRODUCT_CODE", "SOME_OTHER_ERP")

    settings = AppSettings.load()

    assert settings.app_name == "Printing Press ERP"
    assert settings.product_code == "SOME_OTHER_ERP"


def test_a_setting_that_must_be_a_number_says_so(bare_environment, no_config_file, monkeypatch):
    monkeypatch.setenv("MAX_LOGIN_ATTEMPTS", "five")

    with pytest.raises(RuntimeError, match="must be an integer"):
        AppSettings.load()


# ---------------------------------------------------------------- smtp


def test_the_mail_server_is_read_from_the_customers_configuration(bare_environment):
    config = {
        "smtp": {
            "host": "smtp.example.com",
            "port": 465,
            "username": "shop@example.com",
            "from": "noreply@example.com",
            "use_tls": False,
        }
    }

    smtp = SmtpSettings.load(config)

    assert smtp.is_configured
    assert (smtp.host, smtp.port, smtp.username) == ("smtp.example.com", 465, "shop@example.com")
    assert smtp.sender == "noreply@example.com"
    assert smtp.use_tls is False


def test_the_environment_overrides_the_configuration_file(bare_environment, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.localhost")

    smtp = SmtpSettings.load({"smtp": {"host": "smtp.example.com"}})

    assert smtp.host == "smtp.localhost"


def test_the_sender_falls_back_to_the_account_being_signed_in_as(bare_environment):
    smtp = SmtpSettings.load({"smtp": {"host": "smtp.example.com", "username": "shop@example.com"}})

    assert smtp.sender == "shop@example.com"


@pytest.mark.parametrize(
    "port", ["587", 0, -1, None, True], ids=["string", "zero", "negative", "null", "boolean"]
)
def test_a_port_written_as_the_wrong_thing_falls_back_to_the_default(bare_environment, port):
    """A hand-edited file is the only way this arrives, and a shop that
    mistyped a port should still be able to open the application."""
    smtp = SmtpSettings.load({"smtp": {"host": "smtp.example.com", "port": port}})

    assert smtp.port == constants.DEFAULT_SMTP_PORT


def test_a_configuration_file_with_no_mail_block_leaves_mail_off(bare_environment):
    assert not SmtpSettings.load({"licensing": {}}).is_configured


def test_the_mail_password_is_not_part_of_the_settings(bare_environment):
    """It is a secret, so it is read at the moment it is used — never
    carried around in a config object."""
    assert not hasattr(SmtpSettings.load({}), "password")


# ------------------------------------------------------- provisioning


_PROVISIONED = {
    "smtp": {
        "host": "smtp.vendor.example",
        "port": 465,
        "username": "noreply@vendor.example",
        "use_tls": False,
    }
}


def test_a_build_provisioned_with_a_mail_server_needs_no_configuration(bare_environment):
    """The whole point: a customer installs and 'Forgot password' works,
    with no settings.json and nothing saved on the machine."""
    smtp = SmtpSettings.load({}, _PROVISIONED)

    assert smtp.is_configured
    assert (smtp.host, smtp.port, smtp.username) == (
        "smtp.vendor.example",
        465,
        "noreply@vendor.example",
    )
    assert smtp.sender == "noreply@vendor.example"
    assert smtp.use_tls is False


def test_the_customers_own_configuration_overrides_the_build(bare_environment):
    """A shop with its own mail server does not need a new build to use
    it."""
    smtp = SmtpSettings.load({"smtp": {"host": "smtp.theshop.example"}}, _PROVISIONED)

    assert smtp.host == "smtp.theshop.example"
    # Only what was overridden. The rest still comes from the build.
    assert smtp.port == 465


def test_the_environment_still_wins_over_both(bare_environment, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.localhost")

    smtp = SmtpSettings.load({"smtp": {"host": "smtp.theshop.example"}}, _PROVISIONED)

    assert smtp.host == "smtp.localhost"


def test_a_mistyped_setting_falls_back_to_the_build_not_to_nothing(bare_environment):
    """One hand-edited line in settings.json must not cost the shop the
    mail server the build already knew about."""
    smtp = SmtpSettings.load({"smtp": {"port": "465", "use_tls": "yes"}}, _PROVISIONED)

    assert smtp.port == 465
    assert smtp.use_tls is False
