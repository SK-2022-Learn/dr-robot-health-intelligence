import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ComponentType, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FamilyPage from "@/app/family/page";
import { ProfileProvider } from "@/components/health/profile-context";
import { getFamily, getFamilyPatterns, updateFamilyPermission } from "@/lib/api/family";
import { getProfiles } from "@/lib/api/profiles";
import type {
  FamilyConditionPattern,
  FamilyData,
  FamilyPatternsResponse,
  Profile,
} from "@/lib/types/api";

vi.mock("@xyflow/react", () => ({
  Background: () => null,
  Controls: () => null,
  Handle: () => null,
  Position: { Top: "top", Bottom: "bottom" },
  ReactFlow: ({ nodes, edges, nodeTypes, children }: {
    nodes: { id: string; type: string; data: unknown }[];
    edges: { id: string; label?: string }[];
    nodeTypes: Record<string, ComponentType<{ data: unknown }>>;
    children: ReactNode;
  }) => <div data-testid="react-flow">{nodes.map((node) => {
    const Component = nodeTypes[node.type];
    return <Component key={node.id} data={node.data} />;
  })}{edges.map((edge) => <span key={edge.id}>{edge.label}</span>)}{children}</div>,
}));
vi.mock("@/lib/api/profiles", () => ({ getProfiles: vi.fn() }));
vi.mock("@/lib/api/family", () => ({
  getFamily: vi.fn(),
  getFamilyPatterns: vi.fn(),
  updateFamilyPermission: vi.fn(),
}));

const profile: Profile = {
  id: "self",
  owner_user_id: "owner",
  display_name: "Actual name",
  relationship_to_owner: "SELF",
  date_of_birth: null,
  sex: null,
  access_level: "PRIVATE",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const family: FamilyData = {
  requester_user_id: "owner",
  selected_profile_id: "self",
  profiles: [
    { profile_id: "self", label: "Self", relationship_to_owner: "SELF", access_level: "FULL", is_private: false, permission_id: null, documented_condition_count: 1, shared_conditions: ["diabetes"] },
    { profile_id: "parent", label: "Parent A", relationship_to_owner: "MOTHER", access_level: "FULL", is_private: false, permission_id: "permission-parent", documented_condition_count: 1, shared_conditions: ["diabetes"] },
    { profile_id: "summary", label: "Grandparent A", relationship_to_owner: "GRANDMOTHER", access_level: "FAMILY_SUMMARY", is_private: false, permission_id: "permission-summary", documented_condition_count: null, shared_conditions: ["diabetes"] },
    { profile_id: "private", label: "Sibling", relationship_to_owner: "SIBLING", access_level: "PRIVATE", is_private: true, permission_id: "permission-private", documented_condition_count: null, shared_conditions: null },
  ],
  relationships: [
    { id: "rel-1", source_profile_id: "self", target_profile_id: "parent", relationship_type: "MOTHER", created_at: "2026-01-01T00:00:00Z" },
  ],
};

const pattern: FamilyConditionPattern = {
  condition_name: "Diabetes",
  profile_count: 3,
  permitted_profile_count: 3,
  generation_count: 3,
  branches: ["maternal", "self/children"],
  contributing_profiles: [
    { profile_id: "self", label: "Self", access_level: "FULL", state: "DOCUMENTED", generation: 0, branch: "self/children", health_event_id: "event-self", verification_status: "VERIFIED", evidence: [{ health_event_id: "event-self", evidence_path: "/evidence/self", source_count: 1 }] },
    { profile_id: "parent", label: "Parent A", access_level: "FULL", state: "DOCUMENTED", generation: -1, branch: "maternal", health_event_id: "event-parent", verification_status: "VERIFIED", evidence: [] },
    { profile_id: "summary", label: "Grandparent A", access_level: "FAMILY_SUMMARY", state: "DOCUMENTED", generation: -2, branch: "maternal", health_event_id: null, verification_status: null, evidence: [] },
  ],
  profile_states: [],
  evidence_count: 1,
  confidence: "MODERATE",
  statement: "Diabetes is documented in 3 permitted family profiles across 3 generations.",
  notes: ["Private profiles are excluded from all condition counts and evidence."],
};

const patterns: FamilyPatternsResponse = {
  requester_user_id: "owner",
  selected_profile_id: "self",
  patterns: [pattern],
};

function renderPage() {
  return render(<ProfileProvider><FamilyPage /></ProfileProvider>);
}

beforeEach(() => {
  vi.mocked(getProfiles).mockResolvedValue([profile]);
  vi.mocked(getFamily).mockResolvedValue(family);
  vi.mocked(getFamilyPatterns).mockResolvedValue(patterns);
  vi.mocked(updateFamilyPermission).mockResolvedValue({
    permission_id: "permission-summary",
    profile_id: "summary",
    access_level: "PRIVATE",
    scope: "family-health",
  });
});

describe("Phase 10 family UI", () => {
  it("renders the React Flow tree, relationships, shared nodes, and private redaction", async () => {
    renderPage();
    expect(await screen.findByTestId("react-flow")).toBeInTheDocument();
    expect(screen.getByText("Self")).toBeInTheDocument();
    expect(screen.getByText("Private profile")).toBeInTheDocument();
    expect(screen.getByText("Mother")).toBeInTheDocument();
    expect(screen.queryByText("Secret condition")).not.toBeInTheDocument();
    expect(screen.getByText("Family insights use only information permitted for sharing.")).toBeInTheDocument();
    expect(screen.getByText("Patterns are descriptive and are not predictions.")).toBeInTheDocument();
  });

  it("renders deterministic insights and permission-safe WHY evidence", async () => {
    renderPage();
    await screen.findByTestId("react-flow");
    fireEvent.click(screen.getByRole("tab", { name: "Family Insights" }));
    expect(screen.getByText(pattern.statement)).toBeInTheDocument();
    expect(screen.getByText("Data confidence: Moderate")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "WHY?" }));
    expect(screen.getByRole("complementary", { name: "Family pattern evidence" })).toBeInTheDocument();
    expect(screen.getByText("Grandparent A")).toBeInTheDocument();
    expect(screen.getAllByText("Trusted condition evidence")).toHaveLength(1);
    expect(screen.getByText(/Family Summary contributors are counted/)).toBeInTheDocument();
  });

  it("shows the shared table and updates consent with the explicit requester", async () => {
    renderPage();
    await screen.findByTestId("react-flow");
    fireEvent.click(screen.getByRole("tab", { name: "Shared Conditions" }));
    expect(screen.getByRole("table", { name: "Shared family conditions" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View evidence (1)" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Consent & Privacy" }));
    fireEvent.change(screen.getByLabelText("Grandparent A access level"), { target: { value: "PRIVATE" } });
    await waitFor(() => expect(updateFamilyPermission).toHaveBeenCalledWith("permission-summary", "owner", "PRIVATE"));
    expect(getFamily).toHaveBeenCalledWith("self", "owner", expect.any(AbortSignal));
  });

  it("renders an error state without stale family data", async () => {
    vi.mocked(getFamily).mockRejectedValue(new Error("offline"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });
});
