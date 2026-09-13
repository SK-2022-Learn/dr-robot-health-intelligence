"use client";

import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { useCallback, useMemo, useState } from "react";

import { useProfile } from "@/components/health/profile-context";
import { Card, EmptyState, ErrorState, LoadingState, PageHeading, StatusPill } from "@/components/ui";
import { getFamily, getFamilyPatterns, updateFamilyPermission } from "@/lib/api/family";
import { apiAbsoluteUrl } from "@/lib/api/client";
import { useResource } from "@/lib/hooks/use-resource";
import type {
  AccessLevel,
  FamilyConditionPattern,
  FamilyData,
  FamilyProfileSummary,
} from "@/lib/types/api";
import { friendlyLabel } from "@/lib/utils/format";

type Tab = "tree" | "insights" | "shared" | "consent";
type FamilyNodeData = { profile: FamilyProfileSummary };
type FamilyNode = Node<FamilyNodeData, "family">;

const tabs: { id: Tab; label: string }[] = [
  { id: "tree", label: "Family Tree" },
  { id: "insights", label: "Family Insights" },
  { id: "shared", label: "Shared Conditions" },
  { id: "consent", label: "Consent & Privacy" },
];

const permissionHelp: Record<AccessLevel, string> = {
  PRIVATE: "No cross-profile health details or pattern contribution.",
  CAREGIVER: "Detailed records and evidence are available to the designated caregiver.",
  FAMILY_SUMMARY: "Only condition names needed for limited repeated-pattern summaries are shared.",
  FULL: "Detailed records and evidence are available to the authorized user.",
};

function FamilyTreeNode({ data }: NodeProps<FamilyNode>) {
  const profile = data.profile;
  return (
    <article className={`family-node ${profile.is_private ? "private" : "shared"}`} aria-label={`${profile.label} family profile`}>
      <Handle type="target" position={Position.Top} />
      <div className="family-node-head">
        <strong>{profile.label}</strong>
        {profile.relationship_to_owner === "SELF" && <span>YOU</span>}
      </div>
      {profile.is_private ? (
        <p>Private profile</p>
      ) : profile.shared_conditions?.length ? (
        <div className="condition-badges">
          {profile.shared_conditions.map((condition) => <span key={condition}>{condition}</span>)}
        </div>
      ) : (
        <p>No shared condition pattern documented</p>
      )}
      <small>{friendlyLabel(profile.access_level)}</small>
      <Handle type="source" position={Position.Bottom} />
    </article>
  );
}

const nodeTypes = { family: FamilyTreeNode };

function nodePosition(profile: FamilyProfileSummary, index: number): { x: number; y: number } {
  const positions: Record<string, { x: number; y: number }> = {
    GRANDMOTHER: { x: 40, y: 20 },
    GRANDFATHER: { x: 480, y: 20 },
    MOTHER: { x: 140, y: 180 },
    FATHER: { x: 480, y: 180 },
    SELF: { x: 290, y: 350 },
    SIBLING: { x: 590, y: 350 },
    CHILD: { x: 290, y: 510 },
  };
  const base = positions[profile.relationship_to_owner] ?? { x: 40 + index * 230, y: 510 };
  return { x: base.x + (profile.relationship_to_owner === "SIBLING" ? index * 12 : 0), y: base.y };
}

function FamilyTree({ family }: { family: FamilyData }) {
  const nodes = useMemo<FamilyNode[]>(() => family.profiles.map((profile, index) => ({
    id: profile.profile_id,
    type: "family",
    data: { profile },
    position: nodePosition(profile, index),
    initialWidth: 215,
    initialHeight: 130,
    handles: [
      { id: "target", type: "target", position: Position.Top, x: 103, y: -4, width: 8, height: 8 },
      { id: "source", type: "source", position: Position.Bottom, x: 103, y: 126, width: 8, height: 8 },
    ],
    draggable: false,
  })), [family.profiles]);
  const edges = useMemo<Edge[]>(() => family.relationships.map((relationship) => ({
    id: relationship.id,
    source: relationship.source_profile_id,
    target: relationship.target_profile_id,
    sourceHandle: "source",
    targetHandle: "target",
    label: friendlyLabel(relationship.relationship_type),
    type: "smoothstep",
    animated: false,
  })), [family.relationships]);

  return (
    <Card title="Permission-aware family tree" className="family-tree-card">
      <div className="family-flow" aria-label="Family relationship tree">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}
          nodesConnectable={false} nodesDraggable={false} elementsSelectable={false}>
          <Background gap={22} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </Card>
  );
}

function Insights({ patterns, onWhy }: { patterns: FamilyConditionPattern[]; onWhy: (pattern: FamilyConditionPattern) => void }) {
  if (!patterns.length) return <EmptyState title="No repeated conditions" message="No condition is documented in two or more permitted family profiles." />;
  return <div className="family-insight-grid">{patterns.map((pattern) => (
    <Card key={pattern.condition_name} className="family-insight-card">
      <p className="eyebrow">Documented family pattern</p>
      <h2>{pattern.condition_name}</h2>
      <div className="family-pattern-metrics">
        <strong>{pattern.profile_count}<span>permitted profiles</span></strong>
        <strong>{pattern.generation_count}<span>generations</span></strong>
      </div>
      <p>{pattern.statement}</p>
      <div className="family-card-foot"><StatusPill tone={pattern.confidence === "HIGH" ? "good" : "warm"}>Data confidence: {friendlyLabel(pattern.confidence)}</StatusPill><button onClick={() => onWhy(pattern)}>WHY?</button></div>
    </Card>
  ))}</div>;
}

function SharedConditions({ patterns, onWhy }: { patterns: FamilyConditionPattern[]; onWhy: (pattern: FamilyConditionPattern) => void }) {
  return <Card title="Repeated documented conditions">{!patterns.length ? <EmptyState title="No shared conditions" message="Single-profile conditions are not included in this view." /> : <div className="shared-condition-table" role="table" aria-label="Shared family conditions">
    <div role="row" className="shared-condition-head"><span>Condition</span><span>Profiles</span><span>Generations</span><span>Branch</span><span>Evidence</span></div>
    {patterns.map((pattern) => <div role="row" key={pattern.condition_name}><strong>{pattern.condition_name}</strong><span>{pattern.profile_count}</span><span>{pattern.generation_count}</span><span>{pattern.branches.map(friendlyLabel).join(", ")}</span><button onClick={() => onWhy(pattern)}>View evidence ({pattern.evidence_count})</button></div>)}
  </div>}</Card>;
}

function WhyPanel({ pattern, onClose }: { pattern: FamilyConditionPattern; onClose: () => void }) {
  return <aside className="evidence-drawer family-why" aria-label="Family pattern evidence">
    <div className="evidence-drawer-head"><div><p className="eyebrow">WHY?</p><h2>{pattern.condition_name}</h2></div><button onClick={onClose} aria-label="Close family evidence">Close</button></div>
    <div className="evidence-detail">
      <section><h3>Permitted contributors</h3>{pattern.contributing_profiles.map((profile) => <div className="family-contributor" key={profile.profile_id}><strong>{profile.label}</strong><span>{friendlyLabel(profile.branch)} · Generation {profile.generation}</span><StatusPill>{friendlyLabel(profile.access_level)}</StatusPill>{profile.evidence.map((item) => <a key={item.health_event_id} href={apiAbsoluteUrl(item.evidence_path)} target="_blank" rel="noreferrer">Trusted condition evidence</a>)}</div>)}</section>
      <section><h3>Evidence summary</h3><p>{pattern.evidence_count} linked source{pattern.evidence_count === 1 ? "" : "s"} across permitted condition records.</p><p>Family Summary contributors are counted without exposing their underlying record IDs or source details.</p></section>
      <section><h3>Data confidence</h3><StatusPill tone={pattern.confidence === "HIGH" ? "good" : "warm"}>{friendlyLabel(pattern.confidence)}</StatusPill>{pattern.notes.map((note) => <p key={note}>{note}</p>)}</section>
    </div>
  </aside>;
}

function Consent({ family, busyId, onChange }: { family: FamilyData; busyId: string | null; onChange: (profile: FamilyProfileSummary, level: AccessLevel) => void }) {
  return <div className="consent-layout">
    <Card title="Current family access"><div className="consent-list">{family.profiles.map((profile) => <div key={profile.profile_id} className="consent-row"><div><strong>{profile.label}</strong><p>{permissionHelp[profile.access_level]}</p></div><StatusPill tone={profile.is_private ? "warm" : "good"}>{friendlyLabel(profile.access_level)}</StatusPill><label><span>Access level</span><select aria-label={`${profile.label} access level`} value={profile.access_level} disabled={!profile.permission_id || profile.relationship_to_owner === "SELF" || busyId === profile.profile_id} onChange={(event) => onChange(profile, event.target.value as AccessLevel)}>{(Object.keys(permissionHelp) as AccessLevel[]).map((level) => <option value={level} key={level}>{friendlyLabel(level)}</option>)}</select></label></div>)}</div></Card>
    <Card title="What access levels mean"><dl className="permission-definitions">{(Object.entries(permissionHelp) as [AccessLevel, string][]).map(([level, explanation]) => <div key={level}><dt>{friendlyLabel(level)}</dt><dd>{explanation}</dd></div>)}</dl></Card>
  </div>;
}

export default function FamilyPage() {
  const { activeProfile, loading, error } = useProfile();
  const [tab, setTab] = useState<Tab>("tree");
  const [refresh, setRefresh] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [why, setWhy] = useState<FamilyConditionPattern | null>(null);
  const loader = useCallback(async (signal?: AbortSignal) => {
    const profile = activeProfile!;
    const [family, patterns] = await Promise.all([
      getFamily(profile.id, profile.owner_user_id, signal),
      getFamilyPatterns(profile.id, profile.owner_user_id, signal),
    ]);
    return { family, patterns: patterns.patterns };
  }, [activeProfile]);
  const resource = useResource(loader, activeProfile ? `${activeProfile.id}:${refresh}` : null);

  async function changePermission(profile: FamilyProfileSummary, level: AccessLevel) {
    if (!activeProfile || !profile.permission_id) return;
    setBusyId(profile.profile_id);
    setMutationError(null);
    try {
      await updateFamilyPermission(profile.permission_id, activeProfile.owner_user_id, level);
      setWhy(null);
      setRefresh((value) => value + 1);
    } catch {
      setMutationError("The consent setting could not be updated.");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return <LoadingState label="Loading family permissions…" />;
  if (error) return <ErrorState message={error} />;
  return <>
    <PageHeading eyebrow="Permission-aware context" title="Family" description="Separate profiles, consent-controlled sharing, and deterministic summaries of documented conditions." />
    <div className="privacy-banner"><strong>Family insights use only information permitted for sharing.</strong><span>Patterns are descriptive and are not predictions.</span></div>
    <div className="family-tabs" role="tablist" aria-label="Family views">{tabs.map((item) => <button key={item.id} role="tab" aria-selected={tab === item.id} className={tab === item.id ? "active" : ""} onClick={() => { setTab(item.id); setWhy(null); }}>{item.label}</button>)}</div>
    {mutationError && <div role="alert" className="extraction-notice">{mutationError}</div>}
    {resource.loading ? <LoadingState label="Applying family privacy rules…" /> : resource.error ? <ErrorState message={resource.error} /> : resource.data && <div className={`family-layout ${why ? "with-evidence" : ""}`}><main>
      {tab === "tree" && <FamilyTree family={resource.data.family} />}
      {tab === "insights" && <Insights patterns={resource.data.patterns} onWhy={setWhy} />}
      {tab === "shared" && <SharedConditions patterns={resource.data.patterns} onWhy={setWhy} />}
      {tab === "consent" && <Consent family={resource.data.family} busyId={busyId} onChange={changePermission} />}
    </main>{why && <WhyPanel pattern={why} onClose={() => setWhy(null)} />}</div>}
  </>;
}
