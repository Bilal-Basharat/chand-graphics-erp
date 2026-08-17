# Chand Graphics ERP

Offline-first desktop ERP for a small trading or manufacturing business, built with Python and PySide6, designed with a clean architecture so it can later evolve into a multi-tenant SaaS platform and expose web/mobile APIs.

## Project overview

This application manages the operational workflow of a stock-holding business: inventory, sales and purchases with their payments, expenses, reporting, and audit-friendly record keeping.

It is deliberately generic. Where a business needs a catalogue of its own — with its own table, screen and rules, as wedding cards were when this was a printing-press application — that arrives as a *special item module* rather than as changes spread through the app. See "Adding a special item module" below.

The architecture is intentionally designed to support:
- offline desktop usage
- strong separation of concerns
- reusable business logic
- scalable code organization
- later SaaS tenant support
- future REST API or mobile app integration

## Core principles

- Clean Architecture / Hexagonal Architecture
- OOP-first design
- UI separated from business rules
- repository abstraction for data access
- tenant-ready domain model
- testable use cases and services
- secure and maintainable code

## features

- login and role-based access
- inventory and stock levels, filed under cabinets
- sales and purchases with partial payments
- stock movement ledger (adjustment, damage, return, transfer)
- expense tracking
- customer and supplier account ledgers
- profit & loss with real cost of goods sold, and margin by item
- receivables and payables ageing
- audit trail
- local database storage
- backup/export utilities
- tenant-aware foundation for future SaaS

## Tech stack

- Python 3.11+
- PySide6
- SQLAlchemy
- Alembic
- SQLite for offline deployment
- PostgreSQL/MySQL later for SaaS deployment
- pytest for testing

## Architecture notes

The project is split into layers so each part has a clear responsibility:

### Domain
Contains business entities, value objects, enums, and pure business services. This layer must stay independent of the database and UI.

### Application
Contains use cases and DTOs. This is where business workflows are orchestrated.

### Infrastructure
Contains database models, repositories, persistence, audit, backup, and external integrations.

### Presentation
Contains PySide6 windows, widgets, view models, and UI controllers.

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/<your-org>/chand-graphics-erp.git
cd chand-graphics-erp
```

### 2. Create a virtual environment
```bash
python -m venv .venv
```

### 3. Activate it

Windows:
```bash
.venv\Scripts\activate
```

Linux/macOS:
```bash
source .venv/bin/activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure environment (optional)

**Nothing needs configuring to run this.** Every setting has an answer
without a file: application name, version, developer details, product
code and the login-throttle limits all live in `app/config/constants.py`,
which is what this build *is* rather than something a customer sets up.

A `.env` in the checkout can override any of them while developing. It is
loaded **only when running from source** — a packaged build reads no
`.env`, and one must never be bundled into a build (see
[Configuration](#configuration)):

```env
APP_NAME=Printing Press ERP
COMPANY_NAME=Chand Graphics
APP_VERSION=1.0.2
DEVELOPED_BY=Alvi-Systems

MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15

PRODUCT_CODE=CHAND_GRAPHICS_ERP
LICENSE_EXPIRY_WARNING_DAYS=14

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_FROM=
SMTP_USE_TLS=true
```

There is no `SMTP_PASSWORD`, and no initial-admin block: the mail
password is not read from the environment at all, and the first
administrator is created on any empty database — both are covered under
[Configuration](#configuration).

The `SMTP_*` block powers "Forgot password" on the sign-in screen, which
emails a temporary password. It is an override: the account actually used
comes from the build, so for a working "Forgot password" in a checkout,
generate the same bundle a release carries —

```bash
python -m scripts.provision_build
```

— which reads `.env.build` (see [Configuration](#configuration)) and
writes `provisioning.dat` beside it. Leave both out and the button
explains that this copy cannot send email rather than failing.
`SMTP_FROM` defaults to `SMTP_USERNAME`.

### 6. Where the data lives

Run from source, everything is in this checkout: `data/erp.db`,
`config/`, `logs/`.

Installed, it is all under `%LOCALAPPDATA%\ChandGraphicsERP\`:

```
data\    erp.db, session.json, sign_in.json, license.json, installation.json
config\  settings.json
logs\    erp.log (rotating, three kept)
```

Deliberately not beside the executable: replacing the application folder
is exactly what an upgrade does, and `C:\Program Files` needs
administrator rights to write to at all. `ERP_DATA_DIR` overrides the
`data` folder alone — the testing and seeding escape hatch. It is read
from the real environment, not from `.env`.

An installation from an earlier build, which kept its database at the top
of that folder rather than in `data\`, is carried across on first start:
the database, the licence, the installation identity and the saved
session move down together, and the originals are left where they were.

Migrations run by themselves at startup; there is no separate command.
The database records how far it has come in SQLite's `user_version`, and
the first launch of a build with pending changes copies the file to
`erp.v<n>.backup` alongside it before touching anything.

### 7. Start the application
```bash
python -m app.main
```

## Configuration

Four sources, in order of precedence, and a packaged build uses only the
last three:

| Source | Holds | Present in production |
|---|---|---|
| Environment / `.env` | Anything, while developing | **No** |
| `config/settings.json` | What a shop overrides for itself | Yes, if written |
| `provisioning.dat` | The mail account the build sends from | Always |
| `app/config/constants.py` | What this build is | Always |

**`.env` is a development file.** It is loaded only when running from
source, and a frozen build ignores one even if a copy is sitting beside
the executable. It must not be added to a PyInstaller spec: a file beside
the executable is a file the next upgrade replaces, and a developer's own
settings are not a customer's.

**`provisioning.dat` is what the build was packaged with.** A shop that
bought a printing ERP has no mail server and no reason to have one, so
"Forgot password" cannot depend on them configuring one. The vendor's
account is decided once, at build time, and travels inside the
executable. Nothing about it is exposed in the UI and nothing is asked of
the customer.

It is generated during the PyInstaller run from `.env.build` in the
repository root — never committed, covered by the same `.gitignore` rule
as `.env`:

```env
BUILD_SMTP_HOST=smtp.gmail.com
BUILD_SMTP_PORT=587
BUILD_SMTP_USERNAME=someone@example.com
BUILD_SMTP_PASSWORD=<the app password>
BUILD_SMTP_FROM=someone@example.com
BUILD_SMTP_USE_TLS=true
```

Environment variables of the same names win over the file, so a build
machine can inject them without writing one. **Packaging without them
fails the build** rather than producing an installer whose "Forgot
password" is dead; set `ALLOW_UNPROVISIONED_BUILD=1` to mean it.

This is the one secret this application ships. The bundle is encrypted,
but the key is derived in `app/config/provisioning.py` and therefore
travels in the same binary — that stops the password being scraped out of
the install folder with a text search, and nothing more. What limits the
damage is the account: it exists only to send this one message, and
rotating it is one line in `.env.build` and a rebuild. That module says
so at length, and is the place to read before changing any of this.

**`config/settings.json`** is written by whoever sets a machine up — not
shipped, not required, and now an override rather than the only way to
have a mail server at all. Everything in it is optional, and a block here
replaces the build's answer for those keys and leaves the rest alone:

```json
{
  "smtp": {
    "host": "smtp.gmail.com",
    "port": 587,
    "username": "shop@example.com",
    "from": "shop@example.com",
    "use_tls": true
  }
}
```

Nothing in that file is a secret. A value of the wrong type is ignored
rather than obeyed, and a file that has been edited into invalid JSON
leaves the application running on its defaults — a bad afternoon for
whoever edited it, not a reason a shop cannot invoice.

**A machine's own secrets go to the OS credential vault**, never to a
file this application writes. A shop with its own mail server puts its
address and account in `settings.json` and its password here:

```bash
python -m scripts.set_smtp_password           # prompts, stores
python -m scripts.set_smtp_password --show    # is one saved?
python -m scripts.set_smtp_password --forget  # back to the build's
```

This is not part of setting an installation up — an ordinary one needs
none of it. What is saved here wins over what the build carries, so
`--forget` puts a machine back on the vendor's account.

The remembered sign-in password goes to the same vault, under the email
address it belongs to.

**The first administrator.** A database with no users in it gets one:

```
admin@example.com / change-me
```

Change that password immediately on any machine this is installed on. It
is the same in every build — the licence gate stands in front of sign-in,
so the exposure is to someone already at the keyboard, but a shared
default is a shared default. Once any user exists, nothing recreates or
resets it.

**Logs** go to `logs/erp.log`, rotating at about 1 MB with three kept.
That is the first place to look when a customer says the application
closed on them.

## Development workflow

- Keep UI logic inside `presentation/`
- Keep business rules inside `domain/` and `application/`
- Keep database logic inside `infrastructure/`
- Write tests for every use case and repository
- Avoid calling ORM objects directly from UI code
- Use dependency injection through `bootstrap.py`

### Changing the database schema

`create_all()` only ever adds tables that are missing. It will not add a
column to a table that already exists, and it will not remove one — so a
model change alone never reaches a customer's database.

Any change to an existing table needs a step appended to `_STEPS` in
`app/infrastructure/db/upgrade.py`. Write it so running it twice is
harmless, and never reorder or remove an existing step: its position in
that list is the version number recorded in every database in the field.

### Adding a special item module

A *special item module* is a second kind of stocked thing, with its own
table, its own catalogue screen and its own rules — wedding cards, filed
by number under a cabinet, were one. Sales, purchases and the stock
ledger already ask "which kind of item?" on every line, so adding one is
a matter of registering it rather than rewriting them:

1. Add a member to `ItemType` (`app/domain/enums/item_type.py`).
2. Add the entity, repository port, ORM model, mapper and repository, and
   expose the repository on `SqlAlchemyUnitOfWork`.
3. Add its nullable foreign key beside `inventory_item_id` on
   `sale_items`, `purchase_items` and `inventory_movements`, with a CHECK
   naming exactly one target — plus a step in `upgrade.py` that adds the
   column to databases already in the field. Carry the same field onto
   `SaleItem`/`PurchaseItem`/`InventoryMovement` and their commands.
4. Add a branch to `load_stock_target`
   (`app/application/use_cases/stock_helpers.py`) and an entry to
   `_item_column` (`infrastructure/repositories/transaction_repositories.py`).
5. Register it in `ITEM_KINDS` (`app/presentation/item_types.py`): its
   label, how a record names itself, which id a line carries it in, and
   how its catalogue is fetched. Every picker, dropdown and document line
   in the UI is built from that registry and picks it up at once.
6. Add its catalogue screen and route if it needs one of its own, and a
   "movements for this item" use case for the stock ledger.

Nothing else should need to know how many kinds exist.

## Licensing

An installation runs on a signed entitlement — one licence key, verified
on this machine with no Internet. Sales, purchases, inventory and
accounts know nothing about it: the check happens at startup and in the
shell around them, never inside a use case.

**The shape of it.** `LicenseManager` (application) reads a
`LicenseProvider` (domain port). The only implementation today is
`ManualLicenseProvider`: a key the shop was given and typed in. When the
licensing server exists, a `LaravelLicenseProvider` implements the same
three methods and `AppContainer.license_provider()` is the one line that
changes — the rules, the states and both screens stay as they are. The
server will own Product, Customer, Plan, Subscription, Payment, License,
Activation, Entitlement and LicenseEvent; the desktop deliberately holds
none of that, only the signed summary it needs to open offline.

**What is enforced here**: the signature, the product, the expiry and its
grace window, suspension, revocation, and the binding to this
installation. Every installation has its own id and is issued its own key
against it, so one key is one machine and there is no separate device
count to keep.

**Issuing a licence** (vendor side, dev-only — never shipped):

```bash
# Once, on your own machine. Keep the key OUT of this repository.
python -m scripts.licensing.keygen --out C:\keys\chand-licensing.pem --key-id cg-2026-01
# Paste the printed public key into app/infrastructure/licensing/public_keys.py

# Per customer. The installation ID is on their activation dialog.
python -m scripts.licensing.issue_license \
    --private-key C:\keys\chand-licensing.pem \
    --customer "Some Print Shop" \
    --installation-id <their installation id> \
    --expires "13-08-2027 17:30:00" \
    --out shop.lic
```

**`--expires` is an instant, not a day**, because that is what the app
enforces — it compares the clock against `expires_at` to the second, and
grace runs from that same instant. Everything is Pakistan Standard Time
(UTC+5), the clock the application itself reads:

| Written | Signed as |
| --- | --- |
| *omitted* | perpetual |
| `2027-08-13` or `13-08-2027` | `2027-08-13 23:59:59` — the whole of that day |
| `13-08-2027 17:30:45` | exactly that |
| `13-08-2027 17:30` | exactly that, `:00` seconds |
| `2027-08-13T17:30:45` | exactly that (ISO, offset converted to PKT) |

A date on its own means the **end** of that day: "expires 13 August" is
sold and understood as covering 13 August. The tool prints the expiry and
the moment access actually ends, so what was signed is never left to be
worked out from the payload.

Anyone holding the private key can license every installation in the
field, for free, forever. It lives on the vendor's machine, is backed up
there, and never reaches a build. Rotating means publishing a second
public key beside the first and signing new licences with it; licences
already out there keep working until they expire.

**Local state** sits beside the database and never inside it —
`license.json` (the activation) and `installation.json` (this machine's
id). A licence must survive a schema migration and must not travel
through a database restore.

**Renewal, expiry, lockout.** A licence past `expires_at` keeps working
through its `grace_days`, with a warning. After that the ERP does not
open — but the activation dialog still offers both the renewal key and a
backup of the shop's own data, which remains theirs whatever the state of
the account.

**While the app is open.** None of that waits for a restart. When the
licence is read, `next_transition_at` says exactly when the verdict
changes next — the warning window opening, the expiry, the end of grace —
and `LicenseWatcher` arms one single-shot timer for that instant. Nothing
polls. What fires is a re-evaluation against the clock, never the state
that was expected, so a machine that slept through a transition reaches
the right answer anyway; the same re-check runs when the app or the shell
window is activated, and after any activation or renewal.

Each of the three situations is announced once per run — a warning while
the licence still works, and the activation dialog itself once it does
not — with a chip in the status bar carrying the current one for as long
as it lasts. Once the licence stops opening the app, the shell locks: the
two record-something buttons go dark, every destination but Licence and
My profile is refused, and the Licence page is what is left on screen.
Nothing closes and nothing is lost.

**Testing expiry by hand.** Issue a licence a couple of minutes out and
watch a running app deal with it:

```bash
# Locks the app at the printed instant — grace of 0 means expiry is the end.
python -m scripts.licensing.issue_license --private-key C:\keys\chand-licensing.pem \
    --customer "Test" --installation-id <your installation id> \
    --expires "14-08-2026 15:42:00" --grace-days 0 --out test.lic

# Or with grace, to see the amber chip and the "access continues" warning.
#   --expires "14-08-2026 15:42:00" --grace-days 1
```

Paste it into **Settings → Licence → Enter licence key** and leave the app
running. The automated equivalents, which need no waiting at all, are in
`tests/licensing/test_expiry_schedule.py` — they move an injected clock
rather than the system one.

## Testing

Run all tests:
```bash
pytest
```

Run a specific test module:
```bash
pytest tests/unit/test_services.py
```

### Test data

`scripts/seed` fills a database with believable trading so the lists,
period selectors, ledgers and reports have something to show.

```bash
python -m scripts.seed --reset --yes     # six months of trading
python -m scripts.seed --profile smoke   # the fixtures only, no filler
python -m scripts.seed --profile load    # a shop that has been trading for years
python -m scripts.seed --data-dir .\scratch   # somewhere other than data\
python -m scripts.seed --help
```

`load` is the one to use when changing anything about a list screen: a
thousand-odd customers, suppliers, items, cabinets, payment methods and
expense categories, and around two thousand invoices with the purchases,
payments, expenses, stock movements and sign-in history around them. It
takes a few minutes, because every row goes in through the same use case
a person would. The names it generates are meant to be read — "Al-Noor
Printers, Gujranwala", "Matt Paper 130gsm (20x30)" — since a screen full
of "Load Item 00417" says nothing about whether the screen is right at
that size.

It refuses to seed on top of a database that already holds documents,
because the document numbers would collide — pass `--reset` to start from
an empty one. The same `--seed` always produces the same data.

Everything goes in through the application's own use cases, so seeded
data obeys every rule the app enforces. The one exception is dating: no
use case takes "record this as of last March", so rows are created
normally and their dates are corrected afterwards in a single pass, by
`scripts/seed/backdating.py` — the only place in the seeder that writes
SQL.

The dataset is split on purpose. `scripts/seed/dataset.py` writes out by
hand every case a screen has to be able to draw — a part-paid invoice, a
bill with nothing paid against it, a walk-in sale belonging to no
customer, a payment received a month after its invoice, a customer in
credit, an item that is genuinely low on stock — and generates the
routine months around them.

## How profit is worked out

A sale line records `unit_cost` — the quantity-weighted average of every
purchase of that item made up to the day the sale was raised. It is
written once, when the sale is created (`CreateSaleUseCase`), and never
revisited, so buying the item again next month cannot rewrite the margin
on an invoice already handed over. This is what an ERP calls a valuation
rate; weighted average rather than FIFO because FIFO needs a cost-layer
table, and IAS 2 permits either.

Cost of goods sold is then the sum of those line costs, and:

```
gross profit = revenue − cost of goods sold
net profit   = gross profit − expenses
```

Stock **bought** is not in that arithmetic. Paper on a shelf is money
moved, not money gone; it becomes a cost when it is sold. It is shown
beside the figures as context.

An item that has never been purchased has no average, so its `unit_cost`
is NULL. **NULL is not zero** — read as zero it would report the whole
line as profit. Every report counts those lines and says so on screen and
on paper rather than quietly adding them in.

Databases written before this existed are backfilled by migration step 5,
which reconstructs each line the same way the live path computes it,
bounded by that sale's own date.

## Security and compliance goals

This project should be built with:
- role-based authorization
- secure password hashing
- audit logging for critical actions
- tenant isolation from day one
- input validation at the UI and application layers
- safe file handling for exports and backups
- no business logic inside UI event handlers

## Contributing

The codebase should follow these rules:
- prefer small reusable classes
- use type hints
- write docstrings for public methods
- keep functions focused and short
- avoid tight coupling between layers
- add tests with each new feature

## License

Add your preferred license here after deciding whether the repository will be private, internal, or open source.

## Project status

Initial architecture and foundation phase.

