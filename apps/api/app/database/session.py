"""SQLAlchemy engine, session factory, and FastAPI database dependency."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def normalize_database_url(raw_url: str) -> str:
    """Resolve relative SQLite files against the monorepo root.

    This keeps `data/dr_robot.db` in one predictable location regardless of
    whether commands start at the repository root or inside `apps/api`.
    """

    url = make_url(raw_url)
    if url.drivername == "sqlite" and url.database not in {None, "", ":memory:"}:
        database_path = Path(url.database)
        if not database_path.is_absolute():
            url = url.set(database=(REPOSITORY_ROOT / database_path).resolve().as_posix())
    return url.render_as_string(hide_password=False)


def create_database_engine(database_url: str) -> Engine:
    """Create an engine with SQLite connection behavior configured safely."""

    normalized_url = normalize_database_url(database_url)
    is_sqlite = make_url(normalized_url).drivername == "sqlite"
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    database_engine = create_engine(normalized_url, connect_args=connect_args)

    if is_sqlite:
        # SQLite disables foreign-key enforcement per connection unless enabled.
        @event.listens_for(database_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return database_engine


engine = create_database_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide one transaction-aware database session per API request."""

    database_session = SessionLocal()
    try:
        yield database_session
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()
