"""
What this build *is*, as opposed to how an installation is set up.

Application name, version and the developer's own details belong to the
code that was compiled, not to the machine it lands on — a customer
cannot sensibly be asked to configure them, and a build that refuses to
start because one is missing is a build that fails in the field for no
reason. They live here, in one place, and are read straight from Python.

A development checkout may still override any of them through `.env` (see
`app.config.settings`), which is how a spike or a screenshot run points
at different values without touching this file. Production reads no
`.env` at all.

Nothing here is a secret. Passwords, keys and tokens go to the operating
system's credential vault — see `app.infrastructure.security.secret_vault`.
"""
from __future__ import annotations


ITEM_MODULE = "ITEM"
EXPENSE_MODULE = "EXPENSE"

# ------------------------------------------------------------ identity

APP_NAME = "Chand Graphics ERP"
APP_VERSION = "1.0.2"
COMPANY_NAME = "Chand Graphics"

# The folder this application owns under %LOCALAPPDATA%. Changing it
# orphans every installation in the field, so it is fixed for good.
APP_FOLDER_NAME = "ChandGraphicsERP"

# ------------------------------------------------------------ database

# What this build calls its database file. One name, in one place: the
# path, the pre-migration backups and the adoption of an older
# installation are all derived from it.
DATABASE_FILENAME = "erp.db"

# What earlier builds called theirs, newest first. Renaming the database
# in a future build means adding the old name here rather than replacing
# it — a machine that has been trading for a year still has a file under
# the name it was given, and adoption looks for these in order before
# concluding an installation is new.
LEGACY_DATABASE_FILENAMES = ("erp.db",)

# ----------------------------------------------------------- developer

DEVELOPED_BY = "Alvi-Systems"
DEVELOPER_EMAIL = "bilalbisharat@gmail.com"
DEVELOPER_CONTACT = "03042602360"

# ----------------------------------------------------------- licensing

# Which product this build is, as licences name it. One value, in one
# place, so the licence a shop is issued and the licence this build
# accepts cannot drift apart.
DEFAULT_PRODUCT_CODE = "CHAND_GRAPHICS_ERP"

DEFAULT_LICENSE_EXPIRY_WARNING_DAYS = 14

# --------------------------------------------------------------- vault

# The service name credentials are filed under in the OS vault. Visible
# to the user in Windows Credential Manager, so it reads as this
# application. Changing it hides every password already stored.
KEYRING_SERVICE = "Chand Graphics ERP"

# --------------------------------------------------------------- login

DEFAULT_MAX_LOGIN_ATTEMPTS = 5
DEFAULT_LOGIN_LOCKOUT_MINUTES = 15

# ---------------------------------------------------- first-run admin

# The account created on a database that has no users yet, so a fresh
# installation can be signed into at all.
#
# These are the same in every build, which makes changing the password
# the first thing to do on any machine this is installed on — the
# licence gate stands in front of sign-in, so the exposure is to someone
# already at the keyboard, but a shared default is a shared default.
# `EnsureInitialAdminUserUseCase` only ever acts on an empty users
# table, so a changed password is never quietly reset back to this.
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_PASSWORD = "change-me"
DEFAULT_ADMIN_FULL_NAME = "Administrator"
DEFAULT_ADMIN_ROLE = "admin"

# ---------------------------------------------------------------- mail

DEFAULT_SMTP_PORT = 587
