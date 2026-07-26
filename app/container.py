from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.uow import SqlAlchemyUnitOfWork


@dataclass(slots=True)
class AppContainer:
    """
    Simple composition root for the application.

    Right now it only creates the Unit of Work.
    Later it can also provide use cases, services, and other dependencies.
    """

    def create_uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork()