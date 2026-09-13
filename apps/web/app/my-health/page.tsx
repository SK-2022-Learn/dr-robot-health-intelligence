"use client";

import { useCallback } from "react";
import { useProfile } from "@/components/health/profile-context";
import { Card, Disclaimer, EmptyState, ErrorState, LoadingState, PageHeading, StatusPill } from "@/components/ui";
import { getProfileSnapshot } from "@/lib/api/profile-data";
import { useResource } from "@/lib/hooks/use-resource";
import { formatDate, friendlyLabel } from "@/lib/utils/format";

export default function MyHealthPage() {
  const { activeProfile, loading, error } = useProfile();
  const loader = useCallback((signal?: AbortSignal) => getProfileSnapshot(activeProfile!.id, signal), [activeProfile]);
  const resource = useResource(loader, activeProfile?.id ?? null);
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!activeProfile) return <EmptyState title="No profile selected" message="Choose a health profile to view its records." />;
  const conditions = resource.data?.events.filter((item) => item.event_type === "CONDITION") ?? [];
  return <><PageHeading eyebrow="Personal record" title="My Health" description={`Stored observations, medications, and symptoms for ${activeProfile.display_name}.`} />
    {resource.loading ? <LoadingState /> : resource.error ? <ErrorState message={resource.error} /> : resource.data && <div className="dashboard-grid">
      <Card title="Profile"><div className="summary-stack"><div><span>Name</span><strong>{activeProfile.display_name}</strong></div><div><span>Relationship</span><strong>{friendlyLabel(activeProfile.relationship_to_owner)}</strong></div><div><span>Access</span><StatusPill>{friendlyLabel(activeProfile.access_level)}</StatusPill></div></div></Card>
      <Card title="Known conditions">{conditions.length === 0 ? <EmptyState title="No conditions recorded" message="No condition events are stored for this profile." /> : <div className="compact-list">{conditions.map((item) => <div key={item.id}><strong>{item.title}</strong><span>{formatDate(item.event_date)}</span></div>)}</div>}</Card>
      <Card title="Observations" className="span-two">{resource.data.observations.length === 0 ? <EmptyState title="No observations" message="No observations are stored for this profile." /> : <div className="data-table">{resource.data.observations.map((item) => <div className="data-row" key={item.id}><div><strong>{item.display_name}</strong><span>{formatDate(item.observed_at)}</span></div><b>{item.value_number ?? item.value_text ?? "Recorded"} {item.unit ?? ""}</b><StatusPill tone={item.verification_status === "VERIFIED" ? "good" : "warm"}>{friendlyLabel(item.verification_status)}</StatusPill></div>)}</div>}</Card>
      <Card title="Medications">{resource.data.medications.length === 0 ? <EmptyState title="No medications" message="No medication records are stored." /> : <div className="compact-list">{resource.data.medications.map((item) => <div key={item.id}><strong>{item.name}</strong><span>{[item.dose, item.dose_unit, item.frequency].filter(Boolean).join(" ") || "Details not recorded"}</span></div>)}</div>}</Card>
      <Card title="Symptoms">{resource.data.symptoms.length === 0 ? <EmptyState title="No symptoms" message="No symptom records are stored." /> : <div className="compact-list">{resource.data.symptoms.map((item) => <div key={item.id}><strong>{item.name}</strong><span>{item.severity ? `Severity ${item.severity}` : "Severity not recorded"}</span></div>)}</div>}</Card>
      <Card title="Recent health events" className="span-two">{resource.data.events.length === 0 ? <EmptyState title="No health events" message="No health events are stored for this profile." /> : <div className="compact-list">{resource.data.events.slice(0, 5).map((item) => <div key={item.id}><strong>{item.title}</strong><span>{friendlyLabel(item.event_type)} · {formatDate(item.event_date)}</span></div>)}</div>}</Card>
    </div>}<Disclaimer /></>;
}
