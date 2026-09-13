import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Home from "@/app/page";
import TimelinePage from "@/app/timeline/page";
import { ProfileProvider } from "@/components/health/profile-context";
import { Sidebar } from "@/components/layout/sidebar";
import { TopHeader } from "@/components/layout/top-header";
import { getProfileSnapshot } from "@/lib/api/profile-data";
import { getProfiles } from "@/lib/api/profiles";
import { getMissingEvidence, getTimeline } from "@/lib/api/timeline";
import type { HealthEvent, Profile, ProfileSnapshot, TimelineResponse } from "@/lib/types/api";

let pathname = "/";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("next/link", () => ({ default: (props: AnchorHTMLAttributes<HTMLAnchorElement>) => <a {...props} /> }));
vi.mock("@/lib/api/profiles", () => ({ getProfiles: vi.fn() }));
vi.mock("@/lib/api/profile-data", () => ({ getProfileSnapshot: vi.fn() }));
vi.mock("@/lib/api/timeline", () => ({
  getTimeline: vi.fn(),
  getMissingEvidence: vi.fn(),
  getTimelineEvidence: vi.fn(),
}));

const profiles: Profile[] = [
  { id:"profile-self", owner_user_id:"owner", display_name:"Alex Example", relationship_to_owner:"SELF", date_of_birth:null, sex:null, access_level:"PRIVATE", is_active:true, created_at:"2026-01-01T00:00:00Z", updated_at:"2026-01-01T00:00:00Z" },
  { id:"profile-family", owner_user_id:"owner", display_name:"Jordan Example", relationship_to_owner:"SIBLING", date_of_birth:null, sex:null, access_level:"FAMILY_SUMMARY", is_active:true, created_at:"2026-01-01T00:00:00Z", updated_at:"2026-01-01T00:00:00Z" },
];
const event: HealthEvent = { id:"event-1", profile_id:"profile-self", event_type:"LAB_RESULT", event_date:"2026-02-01T00:00:00Z", end_date:null, title:"Example stored event", description:"A test fixture.", verification_status:"VERIFIED", provenance:"DOCUMENT_VERIFIED", confidence:null, source_document_id:null, created_by_user_id:null, created_at:"2026-02-01T00:00:00Z", updated_at:"2026-02-01T00:00:00Z" };
const snapshot: ProfileSnapshot = { events:[event], observations:[], medications:[], symptoms:[], documents:[] };
const timeline: TimelineResponse = {
  profile_id: "profile-self",
  total: 1,
  limit: 100,
  offset: 0,
  items: [{
    id: "health_event:event-1",
    entity_id: "event-1",
    entity_type: "health_event",
    timeline_type: "LAB",
    title: "Example stored event",
    description: "A test fixture.",
    occurred_at: "2026-02-01T00:00:00Z",
    end_at: null,
    date_precision: "EXACT",
    verification_status: "VERIFIED",
    provenance: "DOCUMENT_VERIFIED",
    confidence: null,
    source_type: "DOCUMENT",
    source_document_id: null,
    source_message_id: null,
    has_evidence: true,
    has_correction: false,
    created_at: "2026-02-01T00:00:00Z",
  }],
};

function withProfiles(child: React.ReactNode) {
  return render(<ProfileProvider>{child}</ProfileProvider>);
}

beforeEach(() => {
  pathname = "/";
  vi.mocked(getProfiles).mockResolvedValue(profiles);
  vi.mocked(getProfileSnapshot).mockResolvedValue(snapshot);
  vi.mocked(getTimeline).mockResolvedValue(timeline);
  vi.mocked(getMissingEvidence).mockResolvedValue({ profile_id: "profile-self", gaps: [] });
});

describe("Phase 3 navigation and profile state", () => {
  it("renders every navigation destination and marks the current route", () => {
    pathname = "/timeline";
    render(<Sidebar />);
    expect(screen.getAllByRole("link")).toHaveLength(10);
    expect(screen.getByRole("link", { name: /timeline/i })).toHaveAttribute("aria-current", "page");
  });

  it("loads profiles, defaults to SELF, and changes the selected profile", async () => {
    withProfiles(<TopHeader />);
    const selector = await screen.findByLabelText("Viewing profile");
    expect(selector).toHaveValue("profile-self");
    fireEvent.change(selector, { target: { value: "profile-family" } });
    expect(selector).toHaveValue("profile-family");
  });
});

describe("API-driven pages", () => {
  it("shows a visible loading state while profiles are pending", () => {
    vi.mocked(getProfiles).mockReturnValue(new Promise(() => undefined));
    withProfiles(<Home />);
    expect(screen.getByRole("status")).toHaveTextContent("Preparing your health overview");
  });

  it("renders the Home summary from mocked API data", async () => {
    withProfiles(<Home />);
    expect(await screen.findByText("Example stored event")).toBeInTheDocument();
    expect(screen.getByText("Timeline events")).toBeInTheDocument();
    expect(getProfileSnapshot).toHaveBeenCalledWith("profile-self", expect.any(AbortSignal));
  });

  it("renders the Timeline from mocked API data", async () => {
    withProfiles(<TimelinePage />);
    expect(await screen.findByRole("heading", { name: "Example stored event" })).toBeInTheDocument();
    expect(screen.getByText("Document Verified")).toBeInTheDocument();
    expect(getTimeline).toHaveBeenCalledWith("profile-self", null, "desc", expect.any(AbortSignal));
  });

  it("shows an API error state", async () => {
    vi.mocked(getTimeline).mockRejectedValue(new Error("offline"));
    withProfiles(<TimelinePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });

  it("shows an empty timeline without invented data", async () => {
    vi.mocked(getTimeline).mockResolvedValue({ ...timeline, total: 0, items: [] });
    withProfiles(<TimelinePage />);
    expect(await screen.findByText("No timeline entries")).toBeInTheDocument();
    await waitFor(() => expect(getTimeline).toHaveBeenCalled());
  });
});
