"use client";

import Link from "next/link";

import { ErrorState, LoadingState, StatusPill } from "@/components/ui";
import type { EvidenceResponse } from "@/lib/types/api";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

const provenanceLabels: Record<EvidenceResponse["provenance"], string> = {
  DOCUMENT_VERIFIED: "Document Verified",
  AI_EXTRACTED: "AI Extracted + Reviewed",
  USER_REPORTED: "User Reported",
  USER_CORRECTED: "User Corrected",
  DEVICE_MEASURED: "Device Measured",
  AI_DERIVED: "AI Derived",
};

export function EvidencePanel({
  evidence,
  loading,
  error,
  onClose,
}: {
  evidence: EvidenceResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  return (
    <aside className="evidence-drawer" aria-label="Why this appears">
      <div className="evidence-drawer-head">
        <div>
          <p className="eyebrow">WHY?</p>
          <h2>Where this fact came from</h2>
        </div>
        <button className="secondary-button" onClick={onClose}>Close</button>
      </div>
      {loading ? <LoadingState label="Resolving source evidence..." /> : error ? (
        <ErrorState message={error} />
      ) : evidence && (
        <div className="evidence-detail">
          <div className="pill-row">
            <StatusPill>{provenanceLabels[evidence.provenance]}</StatusPill>
            <StatusPill tone={evidence.verification_status === "VERIFIED" ? "good" : "warm"}>
              {friendlyLabel(evidence.verification_status)}
            </StatusPill>
          </div>

          {evidence.source.type === "DOCUMENT" && (
            <section>
              <span className="evidence-label">Document source</span>
              <h3>{evidence.source.filename}</h3>
              <dl className="evidence-meta">
                <div><dt>Document date</dt><dd>{formatDate(evidence.source.document_date)}</dd></div>
                <div><dt>Page</dt><dd>{evidence.source.page_number ?? "Page unavailable"}</dd></div>
              </dl>
              <blockquote>{evidence.source.excerpt ?? "Source excerpt unavailable."}</blockquote>
              {evidence.source.page_text && (
                <details>
                  <summary>Relevant page text</summary>
                  <pre>{evidence.source.page_text}</pre>
                </details>
              )}
              <Link className="primary-button source-link" href={evidence.source.view_source_path}>
                View Source
              </Link>
            </section>
          )}

          {evidence.source.type === "CHAT" && (
            <section>
              <span className="evidence-label">{evidence.source.label}</span>
              <h3>Original chat message</h3>
              <blockquote>{evidence.source.message}</blockquote>
              <time>{formatDate(evidence.source.message_timestamp)}</time>
              {evidence.saved_value && (
                <div className="saved-value"><span>Saved structured value</span><strong>{evidence.saved_value}</strong></div>
              )}
            </section>
          )}

          {(evidence.source.type === "MANUAL" || evidence.source.type === "DERIVED") && (
            <section>
              <span className="evidence-label">{friendlyLabel(evidence.source.type)} source</span>
              <p>{evidence.source.message}</p>
            </section>
          )}

          <section>
            <span className="evidence-label">Correction history</span>
            {evidence.correction_history.length === 0 ? (
              <p className="helper-text">No corrections recorded.</p>
            ) : evidence.correction_history.map((correction, index) => (
              <article className="correction-card" key={`${correction.corrected_at}-${index}`}>
                <div><span>Original</span><strong>{correction.original_value ?? "Unavailable"}</strong></div>
                <div><span>Corrected</span><strong>{correction.corrected_value ?? "Unavailable"}</strong></div>
                <p>Changed: {correction.changed_fields.map(friendlyLabel).join(", ") || "Reviewed fields"}</p>
                <small>{formatDate(correction.corrected_at)}{correction.actor ? ` · ${correction.actor}` : ""}</small>
              </article>
            ))}
          </section>
        </div>
      )}
    </aside>
  );
}
