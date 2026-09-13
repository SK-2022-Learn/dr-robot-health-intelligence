"""Guardrail tests for destructive demo-database reset behavior."""

from pathlib import Path

import pytest
from reset_demo import validated_database_path

from app.config import Settings


def test_reset_rejects_production() -> None:
    settings = Settings(app_env="production", database_url="sqlite:///./data/dr_robot.db")
    with pytest.raises(RuntimeError, match="development or test"):
        validated_database_path(settings)


def test_reset_rejects_non_sqlite() -> None:
    settings = Settings(app_env="development", database_url="postgresql://localhost/example")
    with pytest.raises(RuntimeError, match="SQLite"):
        validated_database_path(settings)


def test_reset_rejects_sqlite_outside_project_data(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test", database_url=f"sqlite:///{(tmp_path / 'outside.db').as_posix()}"
    )
    with pytest.raises(RuntimeError, match="repository data directory"):
        validated_database_path(settings)
