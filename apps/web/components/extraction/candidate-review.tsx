"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState, ErrorState, LoadingState, StatusPill } from "@/components/ui";
import { DocumentIndexing } from "@/components/retrieval/document-indexing";
import {
  acceptCandidate,
  correctCandidate,
  extractDocument,
  getCandidates,
  rejectCandidate,
} from "@/lib/api/extraction";
import { readableApiError } from "@/lib/api/client";
import type {
  CandidateType,
  ExtractedCandidate,
  SourceDocument,
} from "@/lib/types/api";
import { friendlyLabel } from "@/lib/utils/format";

const groupOrder: CandidateType[] = [
  "condition",
  "medication",
  "lab",
  "symptom",
  "measurement",
];

const immutableFields = new Set(["confidence", "evidence_text", "page_number"]);
const numericFields = new Set(["value_number", "reference_low", "reference_high"]);

function confidenceLabel(value: number): "High" | "Moderate" | "Low" {
  if (value >= 0.85) return "High";
  if (value >= 0.6) return "Moderate";
  return "Low";
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not provided";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function editableInputType(field: string): "number" | "date" | "datetime-local" | "text" {
  if (numericFields.has(field)) return "number";
  if (field.endsWith("_date")) return "date";
  if (field.endsWith("_at")) return "datetime-local";
  return "text";
}

function normalizeInput(field: string, value: string): unknown {
  if (!value) return null;
  if (numericFields.has(field)) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : value;
  }
  return value;
}

function CandidateEditor({
  candidate,
  onCancel,
  onSaved,
}: {
  candidate: ExtractedCandidate;
  onCancel: () => void;
  onSaved: (candidate: ExtractedCandidate) => void;
}) {
  const editable = useMemo(
    () => Object.fromEntries(
      Object.entries(candidate.structured_data).filter(([field]) => !immutableFields.has(field)),
    ),
    [candidate.structured_data],
  );
  const [values, setValues] = useState<Record<string, unknown>>(editable);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const result = await correctCandidate(candidate.id, values);
      onSaved(result.candidate);
    } catch (reason: unknown) {
      setError(readableApiError(reason));
    } finally {
      setSaving(false);
    }
  }

  return <div className="candidate-editor">
    <h4>Correct extracted values</h4>
    <div className="candidate-fields edit-fields">
      {Object.keys(editable).map((field) => <label key={field}>
        <span>{friendlyLabel(field)}</span>
        {field === "active_status" ? <select value={displayValue(values[field]) === "Not provided" ? "" : String(values[field])} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value || null }))}>
          <option value="">Unknown</option><option value="active">Active</option><option value="inactive">Inactive</option>
        </select> : <input
          aria-label={`Correct ${friendlyLabel(field)}`}
          type={editableInputType(field)}
          value={values[field] == null ? "" : String(values[field]).replace("Z", "")}
          onChange={(event) => setValues((current) => ({
            ...current,
            [field]: normalizeInput(field, event.target.value),
          }))}
        />}
      </label>)}
    </div>
    {error && <ErrorState message={error} />}
    <div className="candidate-actions">
      <button className="secondary-button" onClick={onCancel} disabled={saving}>Cancel</button>
      <button className="primary-button" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save Correction"}</button>
    </div>
  </div>;
}

function CandidateCard({
  candidate,
  onUpdate,
}: {
  candidate: ExtractedCandidate;
  onUpdate: (candidate: ExtractedCandidate) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [working, setWorking] = useState<"accept" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const confidence = confidenceLabel(candidate.confidence);
  const fields = Object.entries(candidate.structured_data).filter(
    ([field]) => !immutableFields.has(field),
  );

  async function review(action: "accept" | "reject") {
    setWorking(action);
    setError(null);
    try {
      const result = action === "accept"
        ? await acceptCandidate(candidate.id)
        : await rejectCandidate(candidate.id);
      onUpdate(result.candidate);
    } catch (reason: unknown) {
      setError(readableApiError(reason));
    } finally {
      setWorking(null);
    }
  }

  return <article className={`candidate-card confidence-${confidence.toLowerCase()}`}>
    <div className="candidate-head">
      <div><span className="candidate-type">{friendlyLabel(candidate.candidate_type)}</span><strong>{displayValue(candidate.structured_data.condition_name ?? candidate.structured_data.name ?? candidate.structured_data.test_name ?? candidate.structured_data.measurement_name)}</strong></div>
      <StatusPill tone={candidate.status === "ACCEPTED" || candidate.status === "CORRECTED" ? "good" : candidate.status === "REJECTED" ? "warm" : "neutral"}>{friendlyLabel(candidate.status)}</StatusPill>
    </div>
    <div className="candidate-fields">
      {fields.map(([field, value]) => <div key={field}><span>{friendlyLabel(field)}</span><strong>{displayValue(value)}</strong></div>)}
    </div>
    <div className="confidence-row"><span>Extraction confidence</span><strong>{confidence} ({Math.round(candidate.confidence * 100)}%)</strong></div>
    <div className="evidence-box"><strong>{candidate.page_number ? `Source page: ${candidate.page_number}` : "Page unavailable"}</strong><span>Evidence</span><blockquote>“{candidate.evidence_text}”</blockquote></div>
    {error && <ErrorState message={error} />}
    {editing ? <CandidateEditor candidate={candidate} onCancel={() => setEditing(false)} onSaved={(updated) => { setEditing(false); onUpdate(updated); }} /> : candidate.status === "PENDING" && <div className="candidate-actions">
      <button className="accept-button" onClick={() => review("accept")} disabled={working !== null}>{working === "accept" ? "Accepting…" : "Accept"}</button>
      <button className="secondary-button" onClick={() => setEditing(true)} disabled={working !== null}>Correct / Edit</button>
      <button className="reject-button" onClick={() => review("reject")} disabled={working !== null}>{working === "reject" ? "Rejecting…" : "Reject"}</button>
    </div>}
  </article>;
}

function CandidateReviewPanel({ document }: { document: SourceDocument }) {
  const [candidates, setCandidates] = useState<ExtractedCandidate[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getCandidates(document.id)
      .then((data) => { if (active) setCandidates(data); })
      .catch((reason: unknown) => { if (active) setError(readableApiError(reason)); })
      .finally(() => { if (active) setLoadingCandidates(false); });
    return () => { active = false; };
  }, [document.id]);

  async function extract() {
    setExtracting(true);
    setError(null);
    setMessage(null);
    try {
      const summary = await extractDocument(document.id);
      const rows = await getCandidates(document.id);
      setCandidates(rows);
      setMessage(summary.candidate_count === 0
        ? "Extraction completed. No explicit health facts were found."
        : `${summary.candidate_count} untrusted candidate${summary.candidate_count === 1 ? "" : "s"} ready for review.`);
    } catch {
      setError("Structured extraction could not be completed.");
    } finally {
      setExtracting(false);
    }
  }

  function updateCandidate(updated: ExtractedCandidate) {
    setCandidates((current) => current.map((candidate) => candidate.id === updated.id ? updated : candidate));
  }

  return <section className="extraction-panel">
    <div className="extraction-heading"><div><p className="eyebrow">Human review required</p><h3>AI-assisted structured extraction</h3><p>AI-extracted information is untrusted until you review it.</p></div><div className="extraction-actions">
      <button className="primary-button" onClick={extract} disabled={document.status !== "PARSED" || extracting}>{extracting ? "Extracting…" : "Extract Health Facts"}</button>
      {candidates.length > 0 && <button className="secondary-button" onClick={() => setReviewOpen((open) => !open)}>{reviewOpen ? "Close Review" : "Open Review"}</button>}
    </div></div>
    {loadingCandidates && <LoadingState label="Checking for extraction candidates…" />}
    {message && <div className="extraction-notice" role="status">{message}</div>}
    {error && <div><ErrorState message={error} /><button className="secondary-button retry-button" onClick={extract}>Retry extraction</button></div>}
    {reviewOpen && <div className="candidate-review">
      {candidates.length === 0 ? <EmptyState title="No candidates" message="No structured candidates are available for review." /> : groupOrder.map((type) => {
        const group = candidates.filter((candidate) => candidate.candidate_type === type);
        if (!group.length) return null;
        return <section className="candidate-group" key={type}><h3>{friendlyLabel(`${type}s`)}</h3>{group.map((candidate) => <CandidateCard key={candidate.id} candidate={candidate} onUpdate={updateCandidate} />)}</section>;
      })}
    </div>}
  </section>;
}

export function CandidateReview({ document }: { document: SourceDocument }) {
  return <>
    <DocumentIndexing document={document} onIndexed={async () => undefined} />
    <CandidateReviewPanel document={document} />
  </>;
}
