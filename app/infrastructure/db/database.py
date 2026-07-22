from sqlalchemy import create_engine

from app.config.settings import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)