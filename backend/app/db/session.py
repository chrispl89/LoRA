from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

def _normalize_database_url(url: str) -> str:
    # If user provides "postgresql://", SQLAlchemy defaults to psycopg2.
    # We ship psycopg v3 by default (psycopg[binary]) to support newer Python versions.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


connect_args = {}
db_url = _normalize_database_url(settings.DATABASE_URL)
if db_url.startswith("sqlite"):
    # Required for SQLite when used from multiple threads (FastAPI + Celery worker processes)
    connect_args = {"check_same_thread": False}

engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
