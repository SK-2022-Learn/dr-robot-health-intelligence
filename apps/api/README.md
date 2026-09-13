# Dr. Robot API

FastAPI service for the Dr. Robot prototype.

## Development

From this directory, activate `.venv`, then run:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Create or update the local database schema:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Seed and reset commands run from the repository root and contain only fictional data. The reset command refuses non-SQLite and non-development/test targets.

Tests and quality checks:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```
