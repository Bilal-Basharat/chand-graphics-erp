from sqlalchemy import create_engine, event

from app.config.settings import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()