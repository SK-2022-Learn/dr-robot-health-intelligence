# Architecture

## Phase 13 LangGraph orchestration

```text
START -> safety_pre
          |-- BLOCK / ESCALATE -------------------------------> END
          `-- router
                |-- daily_log -> ChatService pending workflow
                |-- record_lookup -> TimelineService -> optional RetrievalService
                |-- timeline -> TimelineService
                |-- evidence -> EvidenceService
                |-- analytics -> AnalyticsService -> evidence
                |-- family -> FamilyService / PermissionService
                |-- doctor_visit -> DoctorVisitService
                `-- general / unknown -> bounded explanation
                                      |
                                      v
                              safety_post -> END
```

`DrRobotState` is a typed, inspectable state containing identifiers, selected intent, structured service results, source references, warnings, actions, and high-level nodes run. It contains no chain-of-thought. Nodes are thin adapters around existing services; business rules remain in those services. The router is deterministic for supported product intents. Ollama is used only for a general educational explanation or an already-bounded subsystem rewrite, never to calculate analytics, grant permission, promote health facts, or decide safety.

The graph has no repository write node. Daily logging delegates to `ChatService`, which creates only a pending entry until explicit confirmation. Family routing delegates with the selected profile owner as requester and receives only the already-redacted result. Retrieval always supplies the active profile ID and locally revalidates returned Pinecone metadata. Both graph entry and every normally generated response pass the authoritative `SafetyService`; pre-check BLOCK/ESCALATE is the only intentional early return.

Request logs contain request ID, intent, high-level node names, duration, safety decision, and result status. They exclude user queries, prompts, source text, filesystem paths, and credentials. External provider calls retain bounded timeouts. Pinecone failure produces a warning while structured results remain; Ollama failure returns a deterministic fallback for general explanation and does not disable record-backed functions.

## Phase 12 Doctor Visit Mode

```text
Trusted Health Memory
|-- TimelineService
|-- AnalyticsService
|-- EvidenceService
|-- MissingEvidenceService
|-- Medication Repository
`-- Symptom Repository
        |
        v
DoctorVisitService
        |
        v
Structured DoctorVisitBrief
        |
        v
Optional LLM Readability Rewrite
        |
        v
SafetyService
        |
        v
Doctor Visit UI
        |
        v
Print / Save as PDF
```

`DoctorVisitService` is the sole Phase 12 orchestration boundary. It starts with the profile-scoped normalized timeline and retains only `VERIFIED` items. Section builders then resolve authoritative `HealthEvent`, `Medication`, `Observation`, and `Symptom` fields from SQLite. `ExtractedCandidate`, `PendingHealthEntry`, raw chat text, rejected records, and pending or needs-review trusted rows never enter factual sections. No new health facts are created during generation.

Recent changes call the existing deterministic `AnalyticsService.what_changed` contract and embed supported `TrendAnalysisResult` objects unchanged. Evidence labels and actions adapt the existing profile-validating `EvidenceService`. Structural gaps come from `MissingEvidenceService`; Phase 12 adds only explicit medication-reconciliation and missing-recent-thyroid-lab record checks. Discussion questions are deterministic templates keyed to those gaps and supported trends, not recommendations.

The result is a strict, versioned `DoctorVisitBrief` with generation time and data cutoff. A readability rewrite is disabled by default and is limited to the overview. When enabled, the LLM must echo an exact facts fingerprint and preserve numeric tokens. Malformed or contradictory prose falls back to the template. Accepted prose must also pass `SafetyService`; unsafe drafts are discarded and the safety decision is audited. Structured facts are authoritative in every path.

The browser presents patient context, all factual sections, missing evidence, questions, evidence counts, safety notes, source drawers, and analytics calculations. Print media rules remove navigation and interactive controls but keep the summary and visible evidence labels. Generation appends `DOCTOR_VISIT_BRIEF_GENERATED` with identifiers, version, status, and counts only. Doctor Visit Mode summarizes the record for discussion with a healthcare professional. It does not diagnose or prescribe.

## Phase 11 deterministic safety gate

```text
User Input
    |
    v
Safety Pre-Check (SafetyService, safety-v1)
    |-- BLOCK ------> deterministic safe response
    |-- ESCALATE ---> deterministic urgent guidance
    |-- WARN -------> deterministic clinical boundary
    `-- PASS
         |
         v
Normal Application / Structured Extraction Flow
         |
         v
Draft Response
         |
         v
Safety Post-Check
    |-- ALLOW ------> final response
    |-- WARN -------> safe notice / override
    `-- BLOCK ------> deterministic safe override
         |
         v
Typed UI State + Metadata-Only Audit Event
```

`SafetyService` is independent of—and authoritative over—the configured `LLMProvider`. Its deterministic rules, stable IDs, response overrides, and `safety-v1` policy version are centralized under `app/safety`. Pre-checks stop urgent, medication-change, treatment-replacement, diagnosis, prescribing, cure-claim, and obvious dangerous self-treatment workflows before model use. Post-checks inspect any user-facing draft for diagnostic certainty, medication-change or prescribing instructions, and unsupported cure claims. A blocked draft is never returned; fixed safe text replaces it.

The daily chat pipeline records the user message, evaluates the pre-check, and writes a metadata-only audit. Allowed daily logs continue through Phase 7 candidate extraction and explicit confirmation. A small deterministic information layer answers the supported HbA1c definition and profile-scoped latest-record/count questions without broad medical reasoning. Every user-facing draft receives a post-check. Audit actions are `SAFETY_ALLOW`, `SAFETY_WARNING`, `SAFETY_BLOCK`, and `SAFETY_ESCALATION`; payloads contain decision, category, rule ID, policy version, stage, and optional profile ID, but never the user text or draft.

Explicit past/resolved markers and clinician-attributed historical medication statements are handled before intervention rules when they contain no current request or current-symptom marker. This limits the required historical false positives while preserving escalation when wording says the problem is happening now. The rule set is a conservative application boundary, not diagnosis, clinical triage, or proof that unmatched content is medically safe.

## Phase 10 permission-aware family health intelligence

```text
Separate Health Profiles
        |
        v
FamilyRelationship
        |
        v
ConsentPermission
        |
        v
PermissionService
        |
        v
FamilyPatternService
        |
        v
Permission-Safe Pattern Results
        |
        v
Family UI
        |
        v
WHY / Evidence
```

Every person remains a separate `HealthProfile`; family aggregation creates no health fact and copies no record between profiles. Every cross-profile entry point accepts `requester_user_id` explicitly and goes through `FamilyService` and `PermissionService`. The selected family anchor must belong to the requester. The requester's `SELF` profile is `FULL`; for other profiles the newest explicit user consent grant is authoritative, with the original profile access level used only as a compatibility fallback for data created before consent rows existed.

Access behavior is exact: `PRIVATE` returns a generic node and no health details, counts, conditions, sources, or pattern contribution. `FAMILY_SUMMARY` may contribute an exact normalized condition name to a repeated count, but event IDs, verification detail, source paths, and excerpts are redacted. `CAREGIVER` and `FULL` permit condition record identifiers and profile-scoped Phase 8 evidence references. A consent edit changes the grant through service validation and appends `FAMILY_PERMISSION_CHANGED`; safe graph and pattern reads append `FAMILY_PROFILE_VIEWED` and `FAMILY_PATTERN_VIEWED` without health content in audit payloads.

The condition engine is deterministic. It trims whitespace, collapses repeated spaces, and compares case-insensitively; it performs no terminology or synonym inference. Only non-rejected trusted `CONDITION` events in permitted profiles are read, and only conditions documented in at least two permitted profiles become shared patterns. Generations are fixed relative to Self: grandparents `-2`, parents `-1`, self/siblings `0`, children `+1`. Branch is `maternal`, `paternal`, `self/children`, or `unknown`, and a grandparent branch is assigned only when a stored parent-to-grandparent relationship supports it.

Per-profile states are `DOCUMENTED`, `NOT_DOCUMENTED`, `UNKNOWN`, and `PRIVATE`. No stored record never means absence: a detailed profile with other condition documentation can be `NOT_DOCUMENTED` for a particular condition, while an otherwise empty or summary-only profile is `UNKNOWN`. Data confidence is structural, labeled **DATA CONFIDENCE**, and uses contributor count, verification state, and evidence presence. It is not clinical or genetic confidence. Family patterns are descriptive summaries of documented permitted information. They are not diagnoses or predictions.

## Phase 9 deterministic personal baselines and What Changed

```text
Trusted SQLite Observations / Symptoms (VERIFIED only)
        |
        v
  AnalyticsService
  |-- Inclusive, non-overlapping Window Selection
  |-- Metric/context selection and unit Normalization
  |-- Summary Statistics / report-frequency rates
  |-- Deterministic Trend Classification
  |-- Deterministic Data Confidence
  `-- Phase 8 Evidence Collection
        |
        v
  Versioned TrendAnalysisResult
        |
        +--> Optional Explanation Layer (completed calculation only)
        |      `-- mismatch/unavailable -> deterministic template
        v
  Insights UI + API-backed Recharts time series
        |
        v
  WHY Calculation + Evidence
```

For reference date `R` and recent length `N`, the recent window is `[R-(N-1), R]`. The baseline window ends one day before the recent window and extends backward for its configured number of days. Both endpoints are inclusive. Defaults are 30 recent days and 90 baseline days. The query repository applies profile, verified status, and time boundaries in SQLite before metric normalization. Pending/rejected document candidates and pending/rejected chat entries are never queried; only promoted, verified observations and symptoms can participate.

`AnalyticsService` is the authoritative calculator. Numeric summaries include count, mean, median, minimum, maximum, population standard deviation, first value, and last value. It compares period means, returns absolute and percentage change when the baseline mean is suitable, and applies the configured ±5% stability threshold. That threshold describes record movement only and is not a clinical safety threshold. Missing days are never created as zeros. A missing symptom-report period is `INSUFFICIENT_DATA`, because no record does not establish absence.

Glucose contexts are resolved and analyzed independently. Systolic and diastolic blood pressure are parsed and compared independently without hypertension labels. Weight is normalized from kg/lb to kg while evidence retains the original value. Sleep and activity durations are normalized to minutes; activity is explicitly per logged entry, so unlogged days remain unknown. Results use version identifiers (`numeric-trend-v1` and `symptom-frequency-v1`) for reproducibility.

Data confidence is deterministic, is labeled **DATA CONFIDENCE**, and is not clinical confidence. `HIGH` requires at least five verified readings spanning at least half of both windows with no normalization gaps. `MODERATE` requires at least three verified readings in both windows and at most one skipped value. Other sufficient comparisons are `LOW`; comparisons below the configured two-points-per-period minimum are `INSUFFICIENT`.

Every numeric result includes the exact observation IDs and normalized/raw evidence values used. Evidence resolution reuses the profile-scoped Phase 8 `EvidenceService`. The WHY drawer displays windows, calculation, evidence, missing data, confidence reasoning, and calculation version. An optional LLM receives the already-completed result and must echo its classification and means exactly. A contradiction, malformed response, provider failure, or disabled provider causes a deterministic template fallback. The LLM never calculates or overrides a trend. Pinecone is not involved.

## Phase 8 trusted timeline and evidence traceability

```text
Trusted Health Memory
  |-- HealthEvent
  |-- Observation
  |-- Medication
  `-- Symptom
        |
        v
  TimelineService
        |
        v
  Normalized TimelineItem
        |
        v
  EvidenceService
  |-- Document Evidence -> SourceDocument + exact DocumentPage + EvidenceLink
  |-- Chat Evidence     -> immutable Message + Conversation
  `-- Audit History     -> append-only correction event + original/current value
        |
        v
  WHY UI: "Where did this fact come from?"

MissingEvidenceService
        |
        v
Deterministic Record Gaps (missing source, missing date, unverified fact)
```

`TimelineService` is profile-scoped and reads only trusted domain tables. It never reads `ExtractedCandidate` or `PendingHealthEntry` as timeline items, and records with `REJECTED` verification are excluded. The service normalizes entity type, timeline type, title, display value, clinical occurrence/end dates, date precision, provenance, verification, source identifiers, evidence state, and correction state. Sorting uses the clinical/event timestamp; unknown dates are retained in an explicit final group instead of receiving a fabricated date.

`EvidenceService` resolves the requested entity and source under the same profile before returning any content. Document evidence requires the `SourceDocument` to belong to that profile and resolves `DocumentPage` only by the stored page number. Chat evidence follows `source_message_id` through its conversation and returns the immutable original message. A correction response combines the original pending/candidate structure, current trusted value, and append-only audit metadata so discrepancies remain visible. Evidence reads never write to health memory or audit tables.

New document candidate reviews create `EvidenceLink` rows for events, observations, medications, and symptoms. Historical records are not backfilled unless an unambiguous stored relationship exists; missing linkage remains visible rather than being invented. The missing-evidence engine applies only structural rules. It does not use an LLM and does not infer disease progression, risk, treatment need, prognosis, or expected clinical testing.

## Phase 7 daily chat and structured health memory

```text
User Message
  -> Conversation / Message (original text is immutable)
  -> existing LLMProvider structured extraction
  -> Pydantic validation + conservative explicit-fact reconciliation
  -> PendingHealthEntry (server-side, untrusted)
  -> Clarification if required
  -> User Review
       |-- Confirm -> trusted records, USER_REPORTED provenance
       |-- Correct -> revalidate preview, then Confirm with USER_CORRECTED provenance
       `-- Reject  -> retained pending entry, no trusted record
  -> Trusted SQLite Health Memory (Observation / Symptom)
  -> Timeline and My Health
```

Message persistence, extraction parsing, clarification, correction, and confirmation are separate concerns. The centralized prompt permits only explicitly stated facts, requires `null` or `UNKNOWN` for missing context, and prohibits diagnoses, treatment advice, medication changes, and predictive claims. Tests inject the existing fake `LLMProvider`; live validation uses the configured Ollama provider.

`PendingHealthEntry` holds the structured candidate and review status in SQLite, so reloads cannot lose critical state. Clarification answers are restricted to backend-generated field paths and allowlisted values. Glucose without context and weight without a unit cannot be confirmed. The original extraction is retained alongside the edited version, while the source `Message` is never rewritten.

Confirmation is the only trust-boundary transition. It creates verified `Observation` and `Symptom` rows with `source_message_id`, executes all mapped records and the audit entry in one transaction, and rolls everything back on failure. A stored trusted-record manifest makes repeated confirmation idempotent. Conversation and pending-entry profile IDs, foreign keys, and service lookups preserve profile isolation.

Chat audit events record identifiers, profile IDs, counts, changed-state summaries, and clarification field names, but never copy full message text. Conversational records can only use `USER_REPORTED` or `USER_CORRECTED`; the LLM cannot assign `DOCUMENT_VERIFIED`.

## Phase 6 indexing and retrieval flow

```text
Parsed DocumentPage rows (SQLite, authoritative)
  -> explicit Index for Search action
  -> deterministic page-aware chunks (1200 chars, 200 overlap by default)
  -> local Ollama EmbeddingProvider
  -> dimension compatibility check
  -> Pinecone VectorStoreProvider
       namespace: <prefix>-<profile_id>
       metadata filter: profile_id == active profile

Profile-scoped search query
  -> local query embedding
  -> Pinecone namespace + mandatory profile filter
  -> re-resolve document and page in SQLite
  -> verify profile ownership, INDEXED status, and verbatim page occurrence
  -> evidence cards (filename, page, similarity, excerpt)
```

Chunk IDs are stable (`profile:document:page:chunk`) and each chunk retains document ID, profile ID, page number, chunk index, MIME type, original filename, provenance, content hash, and offsets. Reindexing first deletes vectors matching both document and profile, then upserts the deterministic replacement set. Index state, time, safe failure code, and chunk count are stored on `SourceDocument`; full source text and search queries are excluded from audit records.

Profile separation is defense in depth. Each profile uses a distinct Pinecone namespace and every query includes a `profile_id` metadata filter. Retrieved metadata is not trusted: results are discarded unless their document and page resolve locally, belong to the requested profile, are still indexed, and contain the returned excerpt. Invalid vectors are logged by identifier only, without health text.

## Phase 5 extraction and review flow

```text
Document
  -> Parser
  -> Raw Text + DocumentPage
  -> ExtractionService
  -> LLMProvider interface
  -> OllamaProvider / configured local Ollama model
  -> Pydantic validation + verbatim evidence grounding
  -> PENDING ExtractedCandidate (untrusted)
  -> Human Review
       |-- Accept  -> verified trusted record, AI_EXTRACTED provenance
       |-- Correct -> verified trusted record, USER_CORRECTED provenance
       `-- Reject  -> no trusted record
  -> Audit Trail
  -> Trusted Health Memory (accept/correct only)
```

`ExtractionService` depends on the `LLMProvider` protocol, not Ollama directly. The factory selects the provider from environment configuration. Normal tests inject a deterministic fake provider and never require a live model. Ollama receives only page-labelled document content and the extraction instructions; it does not receive filesystem paths, secrets, or unrelated identity metadata.

The model response is not authoritative. Strict Pydantic schemas reject malformed JSON, out-of-range confidence, missing evidence, missing lab/measurement values, and unexpected fields. A second grounding pass requires each evidence quote to occur on its claimed page, or attributes the page when the quote has a source match. Failure creates a safe audit event and no partial candidates or trusted facts.

Candidate creation and trusted-record creation are deliberately separate transactions. Extraction stores immutable model output, evidence, and confidence as `PENDING`. Repeated extraction reuses an existing candidate set instead of duplicating it. Accept, Correct, and Reject revalidate the candidate and operate transactionally. A correction is stored in the trusted record and audit before/after state; it never overwrites the original extraction.

## Phase 4 ingestion flow

```text
Browser
  -> Next.js Upload UI
  -> typed multipart API client
  -> FastAPI versioned API
  -> DocumentService
  -> file validation
  -> profile-isolated local storage
  -> format-specific parser / optional OCR provider
  -> SourceDocument + DocumentPage repositories
  -> SQLite
```

The browser uses one typed API boundary, a shared profile context, and profile-scoped resource loaders. Upload route handlers delegate orchestration to `DocumentService`; validation, generated storage paths, parser selection, format parsing, and persistence remain separate components. PDF and TXT parsers preserve page boundaries. Image OCR is behind a provider interface and safely yields `NEEDS_OCR` when no engine is installed.

Profiles remain distinct records. Duplicate hashes are checked within a profile, storage directories are profile-isolated, and physical filenames are generated from document IDs. APIs expose metadata and page text but never server filesystem paths. Upload, parse, and parse-failure audit entries contain metadata only. Parsing does not create `HealthEvent` rows or otherwise promote raw text into verified health memory.

Post-v1 wellness recommendations and autonomous medical actions are intentionally out of scope.

## Why SQLite

SQLite requires no separate database server and keeps a local MVP simple to run. It now stores structured entities, relationships, dates, provenance, verification state, permissions, and audit history using explicit constraints and migrations.

## Why Pinecone

Pinecone stores embeddings and bounded source-document passage metadata for semantic retrieval, where passages are found by meaning rather than exact field matching. It does not store the authoritative structured health record.

## Why both

Structured queries and vector retrieval solve different problems. SQLite remains the authoritative source for profiles, documents, page text, trusted facts, indexing state, and audits. Pinecone is a derived retrieval index that may be safely rebuilt from parsed pages. Search never mutates trusted SQLite health facts.

## Safety and privacy boundary

Application services keep provenance visible, do not treat extraction, chat, or retrieval as diagnosis, and prevent secrets or raw health records from entering routine logs. AI-extracted information and conversational text are untrusted until a human explicitly reviews and confirms structured data; semantic results are evidence passages, not medical answers. The deterministic Phase 11 gate can allow, warn, block, or escalate, and can replace unsafe drafts. It is not an autonomous diagnostic, prescribing, or comprehensive triage system. Local model and Pinecone availability are reported separately and do not make the core API unhealthy.

Indexing sends chunk text and limited source metadata to Pinecone. That is a real cloud disclosure boundary for sensitive health information even though embedding generation is local. Production deployments must use suitable contractual/compliance controls, least-privilege credentials, an approved region, encryption and retention policies, and profile/document deletion workflows. API keys stay only in environment configuration and are never returned by status APIs.
