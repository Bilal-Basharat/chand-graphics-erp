"""
Save the outgoing mail account's password to this machine's credential vault.

The mail server's address, port and account live in
`config/settings.json`; its password does not — it goes to the operating
system's credential vault, so it is never in a file this application
writes and never inside an installer. This is how it gets there.

    python -m scripts.set_smtp_password
    python -m scripts.set_smtp_password --show      # what is stored now
    python -m scripts.set_smtp_password --forget    # remove it

Run on the machine the application runs on, signed in as the user who
runs it: vault entries belong to a Windows user account, so one saved
under an administrator's login is not there for the shop's own.
"""
from __future__ import annotations

import argparse
import sys
from getpass import getpass

from app.infrastructure.security.secret_vault import SMTP_PASSWORD_KEY, SecretVault


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--show",
        action="store_true",
        help="report whether a password is saved (never prints the password itself)",
    )
    group.add_argument("--forget", action="store_true", help="remove the saved password")
    return parser.parse_args()


def main() -> int:
    arguments = _parse_arguments()
    vault = SecretVault()

    if not vault.is_available:
        print(
            "This machine has no usable credential vault, so the password "
            "cannot be saved. Email sending will stay unavailable.",
            file=sys.stderr,
        )
        return 1

    if arguments.show:
        saved = vault.get(SMTP_PASSWORD_KEY)
        print("A mail password is saved." if saved else "No mail password is saved.")
        return 0

    if arguments.forget:
        vault.delete(SMTP_PASSWORD_KEY)
        print("Removed. 'Forgot password' will stop working until one is saved again.")
        return 0

    password = getpass("Mail account password: ")
    if not password:
        print("Nothing entered; nothing changed.", file=sys.stderr)
        return 1

    if password != getpass("Type it again: "):
        print("The two entries do not match; nothing changed.", file=sys.stderr)
        return 1

    if not vault.set(SMTP_PASSWORD_KEY, password):
        print("The password could not be saved. See the log for why.", file=sys.stderr)
        return 1

    print("Saved to this machine's credential vault.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
