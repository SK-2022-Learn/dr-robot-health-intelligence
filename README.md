# Dr. Robot

Lifetime & Family Health Intelligence

## 1. Project overview

Dr. Robot is a prototype for health information organization, longitudinal memory, and decision support. It provides a monorepo foundation for a browser-based experience and a versioned API.

## 2. Product goal

The long-term goal is to help people organize past records, discuss current context, and understand changes across time and family history while keeping evidence and source material visible.

## 3. Architecture

The browser loads a Next.js application, which communicates with a versioned FastAPI API. Route handlers delegate business rules to services and persistence to repositories backed by SQLAlchemy and SQLite. See [docs/architecture.md](docs/architecture.md).

## 4. Technology stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite, Uvicorn
- Quality: pytest, Ruff, Vitest, Testing Library, ESLint, TypeScript
- Persistence: SQLite for authoritative structured data; Pinecone for profile-isolated semantic retrieval
- Orchestration: LangGraph 1.x sequences existing services behind the unified Ask Dr. Robot API
- Local AI: Ollama for structured extraction, bounded explanations, and `nomic-embed-text` embeddings

## 5. Repository structure

```text
apps/api/       FastAPI application and API tests
apps/web/       Next.js application
packages/       Future cross-application prompts, schemas, and shared material
data/           Local uploads and demonstration data
docs/           Architecture and project documentation
scripts/        Guarded demo seed and reset utilities
tests/          Future repository-level integration tests
```

## 6. Current implementation status

Dr. Robot v1.0.0 is the completed Phase 13 integration. `POST /api/v1/profiles/{profile_id}/ask` runs a typed LangGraph state through mandatory safety pre-check, deterministic intent routing, existing service nodes, bounded explanation, and safety post-check. Supported routes are daily logging, trusted-record lookup, timeline, evidence, deterministic analytics, permission-aware family patterns, Doctor Visit, general education, and explicit unknown/unsupported boundaries. Development clients may request high-level `nodes_run` metadata; prompts and hidden reasoning are never returned.

LangGraph is orchestration only. It cannot write trusted health records, query repositories directly for cross-profile data, override analytics, or bypass safety. Daily writes still require `PendingHealthEntry` confirmation; document facts still require candidate review; family access still goes through `PermissionService`. Pinecone and Ollama failures degrade their optional paths while SQLite timeline, record, analytics, family, and Doctor Visit services remain available.

Phase 12 adds Doctor Visit Mode: a profile-scoped, appointment-ready `DoctorVisitBrief` assembled from trusted SQLite health memory. It combines verified conditions, procedures, hospitalizations, active medications, recent labs, measurements, and symptom reports. Pending or rejected document candidates, unconfirmed chat entries, rejected records, and merely pending trusted-table rows cannot supply facts. The API is `POST /api/v1/profiles/{profile_id}/doctor-visit/generate`; POST is intentional because each generation appends a metadata-only audit event. Generate a fictional validation profile with `scripts/seed_phase12_demo.py` and open `/doctor-visit`.

Recent changes reuse the completed Phase 9 `AnalyticsService` results, including their exact comparison periods, means, classifications, confidence, evidence IDs, and calculation version. Missing-evidence notices reuse the Phase 8 structural-gap service and add conservative medication-reconciliation and missing-recent-thyroid-lab flags. Discussion questions are deterministic and triggered only by those stored gaps or supported trends. Every displayed fact retains its profile-scoped evidence action, while the analytics `WHY?` drawer shows the reproducible calculation.

The brief is generated without Ollama by default. An optional LLM readability rewrite may change only the overview prose: a facts fingerprint, numeric-token check, strict response validation, and the Phase 11 `SafetyService` reject fact changes or unsafe wording and fall back to the deterministic template. Structured sections are never generated or altered by the model. Generation writes only a metadata-only append-only audit event; it does not change health records. Print CSS hides application navigation and controls while preserving the profile, section content, source labels, safety notes, generation time, data cutoff, and summary version for browser **Print / Save as PDF**.

**Doctor Visit Mode summarizes the record for discussion with a healthcare professional. It does not diagnose or prescribe.** It does not recommend medication changes, infer missing facts, or replace professional care.

Phase 11 adds `SafetyService`, an independent deterministic policy gate that is authoritative over response safety. Versioned `safety-v1` rules pre-check urgent symptom reports, medication-change and treatment-replacement requests, autonomous diagnosis requests, prescribing requests, unsupported cure claims, and obvious high-risk self-treatment before normal chat work. Every response draft can also be post-checked for diagnostic certainty, prescribing instructions, medication-change instructions, and cure claims; unsafe drafts are replaced with fixed safe text before display.

Ask Dr. Robot displays normal information, warnings, blocked actions, and urgent escalations as distinct calm states. Safe informational questions and profile-scoped stored-record questions pass, while the Phase 7 review-and-confirm logging flow remains intact. Explicit historical reports such as a resolved 2010 symptom or a clinician instruction from last year are treated as context rather than current requests. Safety audits store only decision, category, stable rule ID, policy version, evaluation stage, and optional profile ID—never full user text, drafts, records, or secrets. **Dr. Robot is not an autonomous diagnostic or prescribing system.**

Phase 10 adds permission-aware family health intelligence over the existing separate profiles, relationships, consent grants, trusted condition events, and evidence links. The family graph returns generic relationship labels and safe access metadata. `PRIVATE` profiles expose no health detail and never contribute to a pattern; `FAMILY_SUMMARY` can contribute only to limited repeated-condition summaries; `CAREGIVER` and `FULL` can expose profile-scoped trusted condition evidence. Every family request passes both the selected profile and requester user explicitly through `FamilyService` and `PermissionService`.

Repeated conditions are counted deterministically using only conservative case/whitespace normalization. A pattern requires two permitted profiles. Generation levels are grandparents `-2`, parents `-1`, self/siblings `0`, and children `+1`; branch labels are used only when stored relationships support them. Missing information is `UNKNOWN` or `NOT_DOCUMENTED`, never absence. **Family patterns are descriptive summaries of documented permitted information. They are not diagnoses or predictions.** Data confidence is structural and is not genetic or clinical confidence. The React Flow family tree, insights, shared-condition table, consent controls, and WHY panel all consume permission-safe API contracts.

Phase 9 adds deterministic What Changed and personal-baseline analytics over verified SQLite observations and symptom reports. The default recent window is the 30 inclusive days ending on the reference date; the personal baseline is the preceding 90 inclusive days and never overlaps the recent period. Glucose, HbA1c, weight, systolic and diastolic blood pressure, sleep duration, activity duration per logged entry, and symptom frequency are supported. Glucose contexts are kept separate, weight is normalized to kg, durations are normalized to minutes, and blood-pressure components are calculated independently.

**Trend classification is deterministic and based on the user's recorded history. It is not a diagnosis.** Numeric comparisons use period means. An absolute percent change of 5% or less is `STABLE`; larger positive or negative changes are `INCREASED` or `DECREASED`. This is an application display threshold, not a medical safety threshold. At least two verified numeric points are required in each period. Missing records remain unknown and are never inserted as zero. Data confidence is also deterministic: `HIGH` requires at least five readings spanning half of both windows with no normalization gaps, `MODERATE` requires at least three readings in both periods with no more than one skipped value, and other sufficient comparisons are `LOW`. Insufficient comparisons use `INSUFFICIENT` data confidence.

The analytics WHY drawer exposes the exact periods, values, units, formula, calculation version, data-confidence reason, evidence source, and missing-data messages. The optional LLM layer receives a completed calculation only. It cannot replace the numeric result, classification, or confidence; a mismatched or unavailable response is discarded in favor of a deterministic template. Core analytics does not require Ollama or Pinecone and makes no causal, diagnostic, treatment, or predictive claim.

Phase 8 replaces table-specific Timeline rendering with a dedicated, profile-scoped `TimelineService`. It combines trusted `HealthEvent`, `Observation`, `Medication`, and `Symptom` records into normalized timeline items, orders them by clinical/event time, supports ascending/descending order and basic type/date pagination filters, and represents genuinely unknown dates without inventing one.

**Timeline includes trusted health memory only.** Pending or rejected document candidates and pending or rejected chat entries are never timeline sources. Records explicitly stored in trusted domain tables may show `VERIFIED`, `PENDING`, or `NEEDS_REVIEW`; records marked `REJECTED` are excluded.

The Timeline WHY interaction answers only “Where did this fact come from?” Document evidence includes safe filename metadata, exact page when known, the grounded excerpt, page text, and a profile-validated View Source path. Chat evidence includes the immutable original message and timestamp. Corrected records display both the original reported/extracted value and the current saved value using append-only audit history. Deterministic missing-evidence notices identify structural gaps such as an absent source or date and do not make clinical recommendations.

Phase 7 adds profile-scoped daily chat and structured health memory for glucose, blood pressure, weight, sleep, activity, and symptoms. A user message is stored unchanged, the configured Phase 5 `LLMProvider` produces a strictly validated candidate extraction, and the server persists that extraction in `PendingHealthEntry`. Missing glucose context and weight units require an allowlisted clarification before review. Only Confirm promotes the reviewed values into verified SQLite observations or symptoms.

**Chat messages are not trusted health memory until structured data is confirmed.** Correcting a preview never changes the original message. Confirmed unchanged entries use `USER_REPORTED` provenance; edited entries use `USER_CORRECTED`; rejected entries remain auditable pending data and create no trusted record. Confirmation is transactional and idempotent.

Phase 6 document indexing and evidence-only semantic search remain available. Parsed pages are deterministically chunked with stable IDs and overlap, embedded locally through Ollama, and stored in Pinecone. Each family profile has a separate namespace, and every query also carries a mandatory `profile_id` metadata filter. Search results are revalidated against SQLite page text before being shown.

The Phase 5 extraction and human-review boundary remains intact. Uploading, parsing, indexing, and semantic search never create or modify trusted health facts. Only an explicit candidate accept or correction can create a verified `HealthEvent`, `Observation`, `Medication`, or `Symptom`. Search returns source passages—not medical answers, diagnoses, recommendations, or generated insights.

Core structured entities include users, distinct family health profiles, family relationships, source-document metadata, longitudinal health events, observations, medications, symptoms, conversations, messages, untrusted extraction candidates, evidence links, consent permissions, and append-only audit logs.

## 7. Requirements

- Python 3.12 or newer
- Node.js LTS and npm
- Git
- Ollama 0.33 or compatible, with the configured extraction and embedding models installed (`qwen3:8b` and `nomic-embed-text:latest` by default)
- A Pinecone serverless index and API key. The index dimension must equal the local embedding dimension (768 for the configured `nomic-embed-text` model).

Docker Desktop is optional for local development and required only for the Compose workflow. Tesseract is optional; valid images are stored with `NEEDS_OCR` status when it is unavailable. Pinecone is required only for indexing and semantic search; the rest of the application remains usable if it is unavailable.

## 8. Local setup

Copy `.env.example` to `.env` only when local overrides are needed. Never commit `.env` files.

Backend setup from the repository root:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Frontend setup:

```powershell
cd apps/web
npm.cmd install
```

Apply database migrations from `apps/api`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

The local database is created at `data/dr_robot.db` and is excluded from source control.

Seed fictional demo data from the repository root:

```powershell
.\apps\api\.venv\Scripts\python.exe .\scripts\seed_demo.py
```

Add the idempotent fictional Doctor Visit validation and empty profiles:

```powershell
.\apps\api\.venv\Scripts\python.exe .\scripts\seed_phase12_demo.py
```

Reset, migrate, and reseed only the guarded development SQLite database:

```powershell
.\apps\api\.venv\Scripts\python.exe .\scripts\reset_demo.py
```

## 9. Backend startup

Confirm that Ollama and the configured model are available:

```powershell
ollama --version
ollama list
Invoke-RestMethod http://localhost:11434/api/version
```

Create a Pinecone dense serverless index with cosine similarity and the exact dimension produced by the embedding model. For `nomic-embed-text:latest` in this project, use dimension `768`. Then configure the untracked root `.env`:

Set local overrides in the untracked root `.env` when necessary. The supplied example uses:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_TIMEOUT_SECONDS=120
AGENT_TIMEOUT_SECONDS=150
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBEDDING_MODEL=nomic-embed-text:latest
EMBEDDING_TIMEOUT_SECONDS=60
VECTOR_PROVIDER=pinecone
PINECONE_API_KEY=replace-with-your-secret
PINECONE_INDEX=dr-robot
PINECONE_NAMESPACE_PREFIX=dr-robot
PINECONE_TIMEOUT_SECONDS=30
CHUNK_SIZE_CHARS=1200
CHUNK_OVERLAP_CHARS=200
```

Do not put a real API key in `.env.example`, source control, screenshots, or logs. Settings and health endpoints expose connection state and index compatibility but never credentials.

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The API exposes metadata and database health plus these current resources:

- `GET /api/v1/health`
- `POST/GET /api/v1/profiles`
- `GET/PATCH /api/v1/profiles/{profile_id}`
- `POST/GET /api/v1/profiles/{profile_id}/events`
- `GET/PATCH /api/v1/events/{event_id}`
- `GET /api/v1/audit` (read-only)
- `GET /api/v1/profiles/{profile_id}/observations`
- `GET /api/v1/profiles/{profile_id}/medications`
- `GET /api/v1/profiles/{profile_id}/symptoms`
- `GET /api/v1/profiles/{profile_id}/documents` (safe metadata only)
- `POST /api/v1/profiles/{profile_id}/documents` (multipart upload)
- `GET /api/v1/documents/{document_id}` (safe document detail)
- `GET /api/v1/documents/{document_id}/pages` (raw page text)
- `POST /api/v1/documents/{document_id}/extract` (create untrusted candidates)
- `POST /api/v1/documents/{document_id}/index` (explicitly index or reindex parsed pages)
- `POST /api/v1/profiles/{profile_id}/retrieval/search` (profile-isolated evidence search)
- `POST/GET /api/v1/profiles/{profile_id}/conversations`
- `GET /api/v1/conversations/{conversation_id}` (messages and persisted pending entries)
- `POST /api/v1/conversations/{conversation_id}/messages` (save message and extract preview)
- `POST /api/v1/chat/pending/{pending_id}/clarify`
- `PATCH /api/v1/chat/pending/{pending_id}` (validate a user correction)
- `POST /api/v1/chat/pending/{pending_id}/confirm` (the only chat-to-memory promotion)
- `POST /api/v1/chat/pending/{pending_id}/reject`
- `GET /api/v1/profiles/{profile_id}/timeline` (`sort`, `type`, `from`, `to`, `limit`, `offset`)
- `GET /api/v1/profiles/{profile_id}/evidence/{entity_type}/{entity_id}`
- `GET /api/v1/profiles/{profile_id}/evidence/gaps`
- `GET /api/v1/profiles/{profile_id}/analytics/trends` (`metric`, optional glucose `context`, reference date, and windows)
- `GET /api/v1/profiles/{profile_id}/analytics/symptoms/{symptom_name}`
- `GET /api/v1/profiles/{profile_id}/analytics/metrics`
- `POST /api/v1/profiles/{profile_id}/analytics/what-changed`
- `GET /api/v1/documents/{document_id}/candidates` (optional `status` filter)
- `POST /api/v1/candidates/{candidate_id}/accept`
- `PATCH /api/v1/candidates/{candidate_id}/correct`
- `POST /api/v1/candidates/{candidate_id}/reject`
- `GET /api/v1/family` (`selected_profile_id`, `requester_user_id` required)
- `GET /api/v1/family/patterns` (optional exact `condition` and `branch` filters)
- `GET /api/v1/family/shared-conditions`
- `GET /api/v1/family/patterns/{condition}/contributors`
- `PATCH /api/v1/family/permissions/{permission_id}`
- `GET /api/v1/system` (non-sensitive status only)

## 10. Frontend startup

In a second terminal:

```powershell
cd apps/web
npm.cmd run dev
```

Open `http://localhost:3000`.

Routes are `/`, `/chat`, `/my-health`, `/family`, `/uploads`, `/search`, `/timeline`, `/insights`, `/doctor-visit`, and `/settings`.

To manually test Phase 11, open **Ask Dr. Robot** and submit each phrase separately. `I have severe chest pain and I can't breathe.` must show the prominent urgent state and emergency guidance without diagnosis. `Should I stop metformin?` must show the medication boundary without dose/change instructions. `Do I have diabetes?` must show the diagnosis boundary. `What does HbA1c measure?` must return safe general information. `Fasting glucose 118 mg/dL` must still create the Phase 7 review preview. `My doctor told me to stop metformin last year.` must remain historical context and must not become a medication boundary. The development-only `POST /api/v1/safety/evaluate` endpoint accepts the normalized safety input contract and supports direct pre/post-check verification. In **Settings**, confirm Safety Policy is Enabled and Version is `safety-v1`. In audit history, verify `SAFETY_ALLOW`, `SAFETY_WARNING`, `SAFETY_BLOCK`, or `SAFETY_ESCALATION` entries contain stable rule/version metadata but no submitted text.

To manually test Phase 9, run `scripts/seed_phase9_demo.py`, open **Insights**, and select **After Meal glucose**. Verify the baseline values `145, 148, 151, 147, 149`, recent values `168, 172, 176, 171, 173`, means `148` and `172 mg/dL`, change `+24 mg/dL`, and `INCREASED` classification. Open WHY and confirm the exact values, dates, inclusive non-overlapping periods, confidence reason, calculation version, and evidence sources. Select Weight for `STABLE`, Sleep duration for `DECREASED`, Activity duration for `INSUFFICIENT_DATA`, and Constipation frequency for the deterministic 2-versus-4 report comparison. The chart must use the evidence values returned by the API. Analytics must continue to return the same numbers with Ollama unavailable.

To manually test Phase 10, run `scripts/seed_phase10_demo.py`, open **Family**, and keep Self selected. Confirm the React Flow tree shows relationship lines, Self is marked, and the sibling node says **Private profile** without a condition name. Family Insights and Shared Conditions must show Diabetes in three permitted profiles across three generations with maternal and self/children branches. Open WHY and verify only Self, Parent A, and Grandparent A appear; Parent A has Family Summary scope and therefore no underlying event/source link. In Consent & Privacy, change Parent A from Family Summary to Private, confirm the Diabetes count falls from three to two, then restore it. Confirm a `FAMILY_PERMISSION_CHANGED` audit exists and no health record count changed.

To manually test Phase 8, open Timeline for the synthetic main profile. Verify records are grouped by year and the unknown-date section remains explicit. Exercise All, Conditions, Labs, Measurements, Medications, and Symptoms. Find the reviewed `HbA1c 7.2 %` document observation, choose **WHY?**, and verify filename, page, excerpt, provenance, and verification; choose **View Source** and confirm the correct page is highlighted. Open WHY for a confirmed chat glucose and verify the original message. For a corrected 181 → 118 chat entry, confirm Timeline shows 118 while evidence shows original 181, saved 118, correction time, actor, and changed field. Review the neutral Missing Evidence panel, then create and reject a distinctive pending chat entry and verify neither state appears on Timeline.

To manually test Phase 7, open **Ask Dr. Robot**, verify the `Logging for` profile, and enter `Morning sugar 118 before food. After breakfast 172. Slept 6 hours. Little constipation. Walked 25 minutes.` Verify all five preview items and check that SQLite trusted-record counts have not changed. Confirm, then verify the new records in My Health and Timeline. Enter `Sugar 165` and choose a context only after the clarification appears. Enter `Weight 72` and verify the kg/lb clarification. Finally, enter `Fasting glucose 181 mg/dL`, edit only the preview to 118, confirm, and verify that chat history still says 181 while trusted memory says 118 with `USER_CORRECTED` provenance. Discard a pending entry and verify it creates no health record.

Relative dates are anchored to the application-local timestamp supplied to the extraction prompt. Explicit dates and times are retained when present; otherwise confirmed entries use the immutable message timestamp. The system does not guess a glucose context or weight unit.

To manually test retrieval, keep Ollama, the API, and frontend available; open `/uploads`; select a profile and a parsed synthetic document; then choose **Index for Search**. The panel shows `NOT_INDEXED`, `INDEXING`, `INDEXED`, or `INDEX_FAILED`, along with chunk count and indexing time. Open `/search`, enter a question, and verify that each result is explicitly labeled **Semantic retrieval result** with filename, page, retrieval similarity, and source excerpt.

Repeat the test with two profiles and distinctive synthetic documents. A query under one profile must never return the other profile's document. Reindexing replaces that document's existing vectors because chunk IDs are stable and document-scoped deletion runs first.

For the Phase 5 manual workflow, upload a synthetic TXT or text PDF, open its detail, select **Extract Health Facts**, then **Open Review**. Inspect every value, source page, evidence quote, and extraction-confidence label. Accept one candidate, correct another, and reject a third. Confirm accepted/corrected values appear in My Health and rejected values do not. A useful correction test is changing a deliberately extracted fasting glucose of 181 mg/dL to 118 mg/dL.

**AI-extracted information is untrusted until reviewed.** High extraction confidence never auto-accepts a fact. Accept creates verified data with `AI_EXTRACTED` provenance; Save Correction creates verified data with `USER_CORRECTED` provenance while preserving the original candidate; Reject retains the candidate and creates no trusted record. Every action is audited without copying full source documents into logs.

Uploads are limited to 15 MB. Allowed types are PDF (`application/pdf`), TXT (`text/plain`), PNG (`image/png`), and JPEG (`image/jpeg`). Files are stored under `data/uploads/<profile-id>/` using the generated document ID, never the supplied filename. Validation checks size, emptiness, declared MIME type, extension, and format signatures; SHA-256 duplicate detection is scoped to one profile. Original filenames remain metadata only. Document statuses are `UPLOADED`, `PROCESSING`, `PARSED`, `NEEDS_OCR`, and `FAILED`.

PDF text is extracted page by page with PyMuPDF. TXT decoding prefers UTF-8 and falls back to Windows-1252. Images are validated with Pillow and OCR is accessed only through an optional provider abstraction. A stored file remains available for retry if parsing fails.

## 11. Testing

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .

cd ../web
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

## 12. Environment variables

Configuration is centralized so infrastructure providers can be changed without modifying business logic. The root `.env.example` documents backend and frontend settings. `apps/web/.env.example` contains the public API base URL used by the browser. `VECTOR_PROVIDER`, Pinecone settings, the embedding provider/model, embedding timeout, chunk size, and overlap are all environment controlled.

`DATABASE_URL` defaults to `sqlite:///./data/dr_robot.db`; relative SQLite paths are resolved from the repository root. Provider interfaces keep Ollama and Pinecone out of retrieval business logic. Secrets belong only in untracked local environment files and must never be logged or committed.

If Settings reports Ollama as unavailable, check that Ollama is running, `OLLAMA_BASE_URL` is reachable, and `OLLAMA_MODEL` exactly matches a name from `ollama list`. No model is downloaded automatically. Extraction returns a controlled temporary-unavailable error without making the rest of the API unhealthy. Malformed or ungrounded model output creates no candidates or trusted records and can be retried from the UI.

## 13. Development phases

- Phase 1: repository, API, frontend, tests, and documentation foundation
- Phase 2: relational domain model, migrations, audited services, APIs, and demo data
- Phase 3: responsive product UI, shared profile context, typed API client, and read-only supporting endpoints
- Phase 4: secure local uploads, raw PDF/TXT parsing, page provenance, and graceful OCR deferral
- Phase 5: configurable Ollama extraction, strict candidate validation, evidence grounding, and human review
- Phase 6: local embeddings, Pinecone indexing, profile isolation, evidence-only semantic search, and retrieval status UI
- Phase 7: daily chat, validated pending health extraction, clarification, human confirmation/correction, provenance, and Timeline/My Health integration
- Phase 8: normalized trusted timeline, document/chat evidence, correction history, source navigation, and deterministic missing-evidence gaps
- Phase 9: deterministic personal baselines, What Changed classification, data confidence, evidence-backed WHY, and API-driven charts
- Phase 10: permission-aware family graph, deterministic shared-condition patterns, privacy redaction, consent controls, and evidence-safe WHY
- Phase 11: deterministic safety pre/post checks, safe overrides, urgent escalation, clinical boundaries, audit metadata, and distinct safety UI states
- Later phases: local agent orchestration and integrated deployment

Features are added only when their phase is explicitly approved.

Current limitations: this is a decision-support prototype, not HIPAA-certified software, an autonomous diagnosis system, or a prescribing system. OCR depends on Tesseract and source scan quality. Extraction, general explanations, and embeddings depend on the configured Ollama model and local hardware. Pinecone semantic search stores intended document chunks and metadata in a cloud service. Family patterns are descriptive, not predictive. Analytics compares personal recorded history and is not clinical interpretation. Historical records without unambiguous source linkage retain a visible evidence gap. PDF visual highlighting is not implemented. Daily logging supports only glucose, blood pressure, weight, sleep, activity, and symptoms. Deterministic safety rules cover explicit patterns and are not comprehensive triage. Settings exposes safe availability labels only.

## 14. Safety boundary

Dr. Robot does not diagnose disease, prescribe treatment, recommend medication changes, validate cure claims, or replace professional medical care. `SafetyService` evaluates text before the normal application flow and evaluates drafts before display. Urgent matches stop casual interpretation and return deterministic emergency guidance. Rule IDs and `safety-v1` are preserved in append-only audits for reproducibility without retaining sensitive prompts.

## 15. Privacy note

Health information is highly sensitive. The project minimizes logging, excludes secrets and raw health data from application logs, and keeps local data artifacts out of source control by default.

SQLite remains the authoritative structured source of truth, and structured SQLite data remains local. Pinecone is a cloud-hosted vector database, so semantic retrieval is not fully offline while Pinecone is enabled. Pinecone contains copied source-document chunks and metadata for retrieval and is therefore a cloud processor of sensitive health text: use an appropriately governed account and region, restrict access, follow retention/deletion requirements, and never treat it as the canonical health record. Ollama embeddings run locally. Retrieval results remain untrusted source evidence. LangGraph sequences permission-safe services and receives no capability to promote data directly into health memory.

## 16. Docker startup

Copy `.env.example` to `.env`, add local credentials, and keep that file uncommitted. On Windows, containers reach host Ollama through `DOCKER_OLLAMA_BASE_URL=http://host.docker.internal:11434`.

```powershell
docker compose config
docker compose build
docker compose up
```

The API starts by applying Alembic migrations. `./data` is bind-mounted at `/data`, preserving SQLite and uploads between container restarts. Pinecone remains external. The public browser API URL is a build argument and contains no secret.

## 17. End-to-end demo

Use only the fictional seed profiles and synthetic reports. Follow [docs/demo.md](docs/demo.md) for the timed walkthrough. The trust-boundary checkpoints are: upload creates no fact; extraction creates pending candidates; only accept/correct promotes a candidate; daily chat creates pending structured data; only confirm promotes it; indexing, analytics, family queries, Doctor Visit, and agent queries do not modify health memory.

## 18. Troubleshooting

- If PowerShell blocks `npm.ps1`, use `npm.cmd`.
- If `node` is not found, install Node.js LTS and append `C:\Program Files\nodejs` to the current PowerShell `PATH`.
- If `/api/v1/system` is slow, confirm Ollama and Pinecone connectivity; the UI allows 15 seconds for bounded provider probes.
- If Ollama is unavailable, run `ollama serve`, verify `/api/version`, and pull the configured models.
- If Pinecone reports a dimension mismatch, recreate the index with the embedding model’s dimension (768 for `nomic-embed-text`).
- If an image remains `NEEDS_OCR`, install Tesseract and make its executable available on `PATH`.
- If SQLite cannot open, confirm the `data` directory is writable and run `alembic upgrade head` from `apps/api`.
- If Windows retains a stale port after a process exits, inspect it with `netstat -ano | findstr :8000`, stop the verified application PID with `taskkill /PID <pid> /T /F`, and restart Windows if the kernel still reports a PID that no longer exists.

## 19. Security and privacy model

Routes validate profile ownership at service boundaries; family aggregation additionally applies explicit consent. Upload validation enforces size, supported MIME/type signatures, generated filenames, and profile-isolated storage. SQLite queries use SQLAlchemy expressions rather than interpolated SQL. CORS allows only `FRONTEND_URL`. API errors use stable envelopes rather than stack traces. Environment secrets are ignored by Git and never returned to the browser. This review is not a formal security assessment or compliance certification.

## 20. Additional guides

- [Architecture](docs/architecture.md)
- [Five-minute demo](docs/demo.md)
- [Developer guide](docs/development.md)
