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
- daily profit/loss reports
- revenue summaries
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

### 5. Configure environment
Create a `.env` file. Every value below is required except the last two,
which fall back to the defaults shown:

```env
APP_NAME=Printing Press ERP
COMPANY_NAME=Chand Graphics
APP_VERSION=1.0.0
DEVELOPED_BY=Alvi-Devs

INITIAL_ADMIN_EMAIL=admin@localhost
INITIAL_ADMIN_PASSWORD=change-me
INITIAL_ADMIN_FULL_NAME=Administrator
INITIAL_ADMIN_ROLE=admin

MAX_LOGIN_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true
```

`APP_VERSION` and `DEVELOPED_BY` are shown in the application's footer.

The `SMTP_*` block is optional and powers "Forgot password" on the sign-in
screen, which emails a temporary password. Leave `SMTP_HOST` blank and the
button explains what to fill in rather than failing. `SMTP_FROM` defaults
to `SMTP_USERNAME`.

### 6. Where the data lives

Run from source, the database is `data/erp.db` in this checkout.

Installed, it is `%LOCALAPPDATA%\ChandGraphicsERP\erp.db` — deliberately
not beside the executable, because replacing the application folder is
exactly what an upgrade does. Set `ERP_DATA_DIR` to override either.

Migrations run by themselves at startup; there is no separate command.
The database records how far it has come in SQLite's `user_version`, and
the first launch of a build with pending changes copies the file to
`erp.v<n>.backup` alongside it before touching anything.

### 7. Start the application
```bash
python -m app.main
```

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
python -m scripts.seed --data-dir .\scratch   # somewhere other than data\
python -m scripts.seed --help
```

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

