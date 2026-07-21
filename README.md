# Chand Graphics ERP

Offline-first desktop ERP for a prining press business built with Python and PySide6, designed with a clean architecture so it can later evolve into a multi-tenant SaaS platform and expose web/mobile APIs.

## Project overview

This application manages the operational workflow of Chand Graphics, including card stock, customer issuance, inventory, expenses, reporting, and audit-friendly record keeping.

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
- card stock management
- card issuance to customers
- inventory management
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
Create a `.env` file or update your config file with values such as:

```env
APP_NAME=Chand Graphics ERP
APP_ENV=development
DATABASE_URL=sqlite:///data/chand_graphics.db
TENANT_MODE=single
LOG_LEVEL=INFO
```

### 6. Run database migrations
```bash
alembic upgrade head
```

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

## Testing

Run all tests:
```bash
pytest
```

Run a specific test module:
```bash
pytest tests/unit/test_services.py
```

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

