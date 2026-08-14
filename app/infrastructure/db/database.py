from sqlalchemy import create_engine, event

from app.config.paths import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # Audit records are written on a second connection while the main
        # one may still hold the write lock. Without a timeout SQLite
        # refuses instantly ("database is locked"); with one it waits its
        # turn, which on a local file is milliseconds.
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()