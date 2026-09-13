# Developer guide

## Backend

From `apps/api` on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health and OpenAPI are at `http://localhost:8000/api/v1/health` and `http://localhost:8000/docs`.

## Frontend

From `apps/web`:

```powershell
$env:Path += ";C:\Program Files\nodejs"
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:3000`. If PowerShell blocks `npm.ps1`, use `npm.cmd` for every npm command.

## Migrations and synthetic data

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m alembic history
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..\..
.\apps\api\.venv\Scripts\python.exe .\scripts\seed_demo.py
.\apps\api\.venv\Scripts\python.exe .\scripts\reset_demo.py
```

`reset_demo.py` refuses non-development/test and non-SQLite targets. Seed scripts are idempotent and contain fictional data only.

## Ollama

Install Ollama, start it, and pull the configured generation and embedding models:

```powershell
ollama serve
ollama pull qwen3:8b
ollama pull nomic-embed-text:latest
Invoke-RestMethod http://localhost:11434/api/version
```

Containerized API processes use `DOCKER_OLLAMA_BASE_URL`, normally `http://host.docker.internal:11434` on Windows.

## Pinecone

Create a cosine serverless index whose dimension matches the embedding model (768 for `nomic-embed-text`). Set `PINECONE_API_KEY`, `PINECONE_INDEX`, and `PINECONE_NAMESPACE_PREFIX` only in the uncommitted `.env`. Every document/query is namespaced and metadata-filtered by profile. Pinecone is cloud-hosted and receives intended document chunks and limited metadata, not authoritative structured SQLite records.

## Tests

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .

cd ..\web
npm.cmd test
npm.cmd run lint
npm.cmd run typecheck -- --incremental false
npm.cmd run build
```

Normal tests use fake LLM, embedding, and vector providers. Live Pinecone/Ollama checks are optional acceptance checks.

## Docker

From the repository root:

```powershell
docker compose config
docker compose build
docker compose up
```

Compose bind-mounts `./data` for SQLite and uploads. No secret is embedded in Dockerfiles or Compose.

## Common Windows issues

- `node`/`npm` not found: install Node.js LTS, reopen PowerShell, or append `C:\Program Files\nodejs` to `PATH`.
- `npm.ps1` execution-policy failure: use `npm.cmd`.
- SQLite lock: stop duplicate API processes and retry.
- Ollama unavailable from Docker: verify `DOCKER_OLLAMA_BASE_URL` and host firewall access.
- Pinecone mismatch: recreate the index at the configured embedding dimension.
- Image stays `NEEDS_OCR`: install Tesseract and expose it on `PATH`.
