"use client";

import { useCallback, useState } from "react";

import { AnalyticsWhyPanel } from "@/components/analytics/analytics-why-panel";
import { useProfile } from "@/components/health/profile-context";
import { EvidencePanel } from "@/components/timeline/evidence-panel";
import {
  Card,
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeading,
  StatusPill,
} from "@/components/ui";
import { readableApiError } from "@/lib/api/client";
import { generateDoctorVisitBrief } from "@/lib/api/doctor-visit";
import { getTimelineEvidence } from "@/lib/api/timeline";
import { useResource } from "@/lib/hooks/use-resource";
import type {
  DoctorVisitObservation,
  EvidenceResponse,
  TrendAnalysisResult,
  VisitEvidenceReference,
} from "@/lib/types/api";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

function displayDateTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function EvidenceAction({
  reference,
  onOpen,
}: {
  reference: VisitEvidenceReference;
  onOpen: (reference: VisitEvidenceReference) => void;
}) {
  return (
    <div className="doctor-visit-evidence">
      <span>{reference.source_label}</span>
      <button onClick={() => onOpen(reference)}>View Evidence</button>
    </div>
  );
}

function ObservationList({
  items,
  emptyTitle,
  emptyMessage,
  onEvidence,
}: {
  items: DoctorVisitObservation[];
  emptyTitle: string;
  emptyMessage: string;
  onEvidence: (reference: VisitEvidenceReference) => void;
}) {
  if (!items.length) return <EmptyState title={emptyTitle} message={emptyMessage} />;
  return (
    <div className="doctor-visit-list">
      {items.map((item) => (
        <article key={item.record_id}>
          <div className="doctor-visit-row-head">
            <div><strong>{item.name}</strong><span>{formatDate(item.observed_at)}</span></div>
            <strong className="doctor-visit-value">{item.value}{item.unit ? ` ${item.unit}` : ""}</strong>
          </div>
          {item.interpretation && <p>{item.interpretation}</p>}
          <EvidenceAction reference={item.evidence} onOpen={onEvidence} />
        </article>
      ))}
    </div>
  );
}

export default function DoctorVisitPage() {
  const { activeProfile, loading, error } = useProfile();
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [why, setWhy] = useState<TrendAnalysisResult | null>(null);
  const loader = useCallback(
    () => generateDoctorVisitBrief(activeProfile!.id),
    [activeProfile],
  );
  const brief = useResource(loader, activeProfile?.id ?? null);

  async function openEvidence(reference: VisitEvidenceReference) {
    if (!activeProfile) return;
    setWhy(null);
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(true);
    try {
      setEvidence(await getTimelineEvidence(
        activeProfile.id,
        reference.entity_type,
        reference.entity_id,
      ));
    } catch (reason: unknown) {
      setEvidenceError(readableApiError(reason));
    } finally {
      setEvidenceLoading(false);
    }
  }

  if (loading) return <LoadingState label="Loading profile..." />;
  if (error) return <ErrorState message={error} />;
  if (!activeProfile) {
    return <EmptyState title="No profile selected" message="Choose a profile to prepare a visit brief." />;
  }

  return (
    <>
      <div className="doctor-visit-heading">
        <PageHeading
          eyebrow="Visit preparation"
          title={`Doctor Visit Brief — ${activeProfile.display_name}`}
          description="A concise, factual review of trusted records for a conversation with a healthcare professional."
        />
        <button className="primary-button doctor-visit-print" onClick={() => window.print()}>
          Print / Save as PDF
        </button>
      </div>

      {brief.loading ? <LoadingState label="Assembling trusted records..." /> : brief.error ? (
        <ErrorState message={brief.error} />
      ) : brief.data && (
        <div className="doctor-visit-layout">
          <main className="doctor-visit-main">
            <section className="doctor-visit-cover">
              <div>
                <p className="eyebrow">Prepared profile</p>
                <h2>{brief.data.profile_display_name}</h2>
                <p>
                  {brief.data.profile_age === null ? "Age not recorded" : `Age ${brief.data.profile_age}`}
                  {brief.data.date_of_birth ? ` · Born ${formatDate(brief.data.date_of_birth)}` : ""}
                  {` · ${friendlyLabel(brief.data.relationship_to_owner)}`}
                </p>
              </div>
              <dl>
                <div><dt>Generated</dt><dd>{displayDateTime(brief.data.generated_at)}</dd></div>
                <div><dt>Data through</dt><dd>{displayDateTime(brief.data.data_cutoff)}</dd></div>
                <div><dt>Summary version</dt><dd>{brief.data.summary_version}</dd></div>
              </dl>
              <p className="doctor-visit-overview">{brief.data.overview}</p>
            </section>

            <div className="doctor-visit-grid">
              <Card title="Known History">
                {!brief.data.known_history.length ? (
                  <EmptyState title="No known history recorded" message="No verified condition, procedure, or hospitalization records are stored." />
                ) : <div className="doctor-visit-list">{brief.data.known_history.map((item) => (
                  <article key={item.record_id}>
                    <div className="doctor-visit-row-head">
                      <div><strong>{item.title}</strong><span>{formatDate(item.documented_date)}</span></div>
                      <StatusPill>{friendlyLabel(item.timeline_type)}</StatusPill>
                    </div>
                    <EvidenceAction reference={item.evidence} onOpen={openEvidence} />
                  </article>
                ))}</div>}
              </Card>

              <Card title="Recent Changes">
                {!brief.data.recent_changes.length ? (
                  <EmptyState title="No supported recent changes" message="There is not enough verified data for a personal-baseline comparison." />
                ) : <div className="doctor-visit-list">{brief.data.recent_changes.map((item) => (
                  <article key={item.key}>
                    <div className="doctor-visit-row-head">
                      <strong>{item.analysis.metric_label}{item.analysis.context ? ` · ${friendlyLabel(item.analysis.context)}` : ""}</strong>
                      <StatusPill>{friendlyLabel(item.analysis.classification)}</StatusPill>
                    </div>
                    <p>{item.statement}</p>
                    <div className="doctor-visit-change-metrics">
                      <span>Recent mean <strong>{item.analysis.recent_summary.mean ?? "Unavailable"} {item.analysis.unit}</strong></span>
                      <span>Baseline mean <strong>{item.analysis.baseline_summary.mean ?? "Unavailable"} {item.analysis.unit}</strong></span>
                    </div>
                    <div className="doctor-visit-evidence">
                      <span>Personal baseline · {friendlyLabel(item.analysis.confidence)} confidence</span>
                      <button onClick={() => { setEvidence(null); setWhy(item.analysis); }}>WHY?</button>
                    </div>
                  </article>
                ))}</div>}
              </Card>

              <Card title="Current Medications">
                {!brief.data.medications.length ? (
                  <EmptyState title="No current medications recorded" message="No verified active medication records are stored." />
                ) : <div className="doctor-visit-list">{brief.data.medications.map((item) => (
                  <article key={item.record_id}>
                    <div className="doctor-visit-row-head">
                      <div><strong>{item.name}</strong><span>{[item.dose, item.dose_unit, item.frequency, item.route].filter(Boolean).join(" ") || "Details not recorded"}</span></div>
                      {item.reconciliation_needed && <StatusPill tone="warm">Reconcile</StatusPill>}
                    </div>
                    <p>Last updated {formatDate(item.last_updated_at)}</p>
                    <EvidenceAction reference={item.evidence} onOpen={openEvidence} />
                  </article>
                ))}</div>}
              </Card>

              <Card title="Recent Labs">
                <ObservationList items={brief.data.recent_labs} emptyTitle="No recent labs recorded" emptyMessage="No verified lab results are stored in the selected recent period." onEvidence={openEvidence} />
              </Card>

              <Card title="Recent Measurements">
                <ObservationList items={brief.data.recent_measurements} emptyTitle="No recent measurements recorded" emptyMessage="No verified measurements are stored in the selected recent period." onEvidence={openEvidence} />
              </Card>

              <Card title="Recent Symptoms">
                {!brief.data.recent_symptoms.length ? (
                  <EmptyState title="No recent symptoms recorded" message="No verified symptom reports are stored in the selected recent period." />
                ) : <div className="doctor-visit-list">{brief.data.recent_symptoms.map((item) => (
                  <article key={item.name}>
                    <div className="doctor-visit-row-head"><strong>{item.name}</strong><span>{formatDate(item.most_recent)}</span></div>
                    <p>{item.statement}</p>
                    {item.evidence[0] && <EvidenceAction reference={item.evidence[0]} onOpen={openEvidence} />}
                  </article>
                ))}</div>}
              </Card>

              <Card title="Missing Evidence">
                {!brief.data.missing_evidence.length ? (
                  <EmptyState title="No structural gaps found" message="No expected source, date, or review gaps were detected in this brief." />
                ) : <div className="doctor-visit-list doctor-visit-gaps">{brief.data.missing_evidence.map((item, index) => (
                  <article key={`${item.type}-${item.entity_id ?? index}`}>
                    <StatusPill tone="warm">{friendlyLabel(item.type)}</StatusPill>
                    <p>{item.message}</p>
                  </article>
                ))}</div>}
              </Card>

              <Card title="Questions to Discuss">
                {!brief.data.questions_to_discuss.length ? (
                  <EmptyState title="No questions generated" message="No record-based clarification questions were triggered." />
                ) : <ol className="doctor-visit-questions">{brief.data.questions_to_discuss.map((item) => (
                  <li key={item.question_id}>{item.question}</li>
                ))}</ol>}
              </Card>

              <Card title="Evidence Summary">
                <div className="doctor-visit-summary">{brief.data.evidence_summary.map((item) => (
                  <div key={item.key}><strong>{item.count}</strong><span>{item.label}</span></div>
                ))}</div>
                <p className="helper-text">Only verified health records contribute factual content to this brief.</p>
              </Card>
            </div>

            <section className="doctor-visit-safety" aria-label="Safety notes">
              {brief.data.safety_notes.map((note) => <p key={note}>{note}</p>)}
            </section>
            <Disclaimer />
          </main>

          {(evidenceLoading || evidenceError || evidence) && (
            <EvidencePanel
              evidence={evidence}
              loading={evidenceLoading}
              error={evidenceError}
              onClose={() => { setEvidence(null); setEvidenceError(null); }}
            />
          )}
          {why && <AnalyticsWhyPanel result={why} onClose={() => setWhy(null)} />}
        </div>
      )}
    </>
  );
}
