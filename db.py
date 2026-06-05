"""
Database setup.

Uses SQLite for now (a single local file, zero setup). Switch to Postgres later
by changing DATABASE_URL.
"""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./app.db"

# check_same_thread=False is needed for SQLite + FastAPI (requests run on
# different threads). Harmless to leave for other databases.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create tables that don't exist yet. Called once at startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: hands each request its own DB session."""
    with Session(engine) as session:
        yield session