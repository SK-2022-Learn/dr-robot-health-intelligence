"""Safely reset only the configured development/test SQLite database."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
DATA_ROOT = (REPOSITORY_ROOT / "data").resolve()
sys.path.insert(0, str(API_ROOT))

from seed_demo import seed_demo  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.database.session import normalize_database_url  # noqa: E402


def validated_database_path(settings: Settings) -> Path:
    """Refuse resets outside a local development/test SQLite data directory."""

    if settings.app_env.lower() not in {"development", "test"}:
        raise RuntimeError("Reset is allowed only in development or test environments.")

    url = make_url(normalize_database_url(settings.database_url))
    if url.drivername != "sqlite" or url.database in {None, "", ":memory:"}:
        raise RuntimeError("Reset requires a file-based SQLite DATABASE_URL.")

    database_path = Path(url.database).resolve()
    if not database_path.is_relative_to(DATA_ROOT):
        raise RuntimeError("Reset target must remain inside the repository data directory.")
    return database_path


def reset_demo() -> None:
    settings = get_settings()
    database_path = validated_database_path(settings)
    if database_path.exists():
        database_path.unlink()

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        check=True,
    )
    seed_demo()
    print(f"Development demo database reset: {database_path}")


if __name__ == "__main__":
    reset_demo()
