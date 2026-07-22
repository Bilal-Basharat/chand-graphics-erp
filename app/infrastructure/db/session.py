from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.database import engine

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True
)