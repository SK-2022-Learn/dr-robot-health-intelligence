import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InsightsPage from "@/app/insights/page";
import { ProfileProvider } from "@/components/health/profile-context";
import {
  getAvailableMetrics,
  getSymptomFrequency,
  getTrend,
  getWhatChanged,
} from "@/lib/api/analytics";
import { getProfiles } from "@/lib/api/profiles";
import type {
  Profile,
  SymptomFrequencyResult,
  TrendAnalysisResult,
} from "@/lib/types/api";

vi.mock("next/link", () => ({ default: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a {...props} /> }));
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  Line: () => null,
  ReferenceLine: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));
vi.mock("@/lib/api/profiles", () => ({ getProfiles: vi.fn() }));
vi.mock("@/lib/api/analytics", () => ({
  getAvailableMetrics: vi.fn(),
  getSymptomFrequency: vi.fn(),
  getTrend: vi.fn(),
  getWhatChanged: vi.fn(),
}));

const profile: Profile = {
  id: "profile-a",
  owner_user_id: "owner",
  display_name: "Alex Example",
  relationship_to_owner: "SELF",
  date_of_birth: null,
  sex: null,
  access_level: "PRIVATE",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function numericResult(overrides: Partial<TrendAnalysisResult> = {}): TrendAnalysisResult {
  return {
    profile_id: profile.id,
    metric: "glucose",
    metric_label: "Glucose",
    context: "AFTER_MEAL",
    unit: "mg/dL",
    reference_date: "2026-09-13",
    recent_period: { start: "2026-08-15", end: "2026-09-13", days: 30, boundaries: "inclusive" },
    baseline_period: { start: "2026-05-17", end: "2026-08-14", days: 90, boundaries: "inclusive" },
    recent_count: 2,
    baseline_count: 2,
    recent_summary: { count: 2, mean: 172, median: 172, minimum: 168, maximum: 176, standard_deviation: 4, first_value: 168, last_value: 176 },
    baseline_summary: { count: 2, mean: 148, median: 148, minimum: 145, maximum: 151, standard_deviation: 3, first_value: 145, last_value: 151 },
    absolute_change: 24,
    percent_change: 16.2162,
    classification: "INCREASED",
    confidence: "LOW",
    confidence_reason: "Minimum counts are met, but sample size or time coverage is limited.",
    missing_data: [],
    evidence_ids: ["baseline-1", "recent-1"],
    evidence: [
      {
        observation_id: "baseline-1",
        recorded_at: "2026-06-01T08:00:00Z",
        original_value: "145 mg/dL",
        normalized_value: 145,
        normalized_unit: "mg/dL",
        provenance: "DOCUMENT_VERIFIED",
        verification_status: "VERIFIED",
        source_type: "DOCUMENT",
        source_label: "labs.txt, page 1",
        source_excerpt: "Glucose 145 mg/dL",
        view_source_path: "/uploads?document=doc-1&page=1",
        evidence_path: "/api/v1/profiles/profile-a/evidence/observation/baseline-1",
      },
      {
        observation_id: "recent-1",
        recorded_at: "2026-09-01T08:00:00Z",
        original_value: "168 mg/dL",
        normalized_value: 168,
        normalized_unit: "mg/dL",
        provenance: "USER_REPORTED",
        verification_status: "VERIFIED",
        source_type: "CHAT",
        source_label: "USER-REPORTED SOURCE",
        source_excerpt: "Post-meal glucose 168 mg/dL",
        view_source_path: null,
        evidence_path: "/api/v1/profiles/profile-a/evidence/observation/recent-1",
      },
    ],
    calculation_version: "numeric-trend-v1",
    stability_threshold_percent: 5,
    explanation: "Your recent after meal glucose average was 172 mg/dL compared with 148 mg/dL in your personal baseline.",
    explanation_source: "TEMPLATE",
    display_priority: 1,
    ...overrides,
  };
}

const stable = numericResult({
  metric: "weight",
  metric_label: "Weight",
  context: null,
  unit: "kg",
  recent_summary: { count: 4, mean: 70.25, median: 70.25, minimum: 70.1, maximum: 70.4, standard_deviation: 0.1, first_value: 70.2, last_value: 70.3 },
  baseline_summary: { count: 4, mean: 70.15, median: 70.15, minimum: 70, maximum: 70.3, standard_deviation: 0.1, first_value: 70, last_value: 70.3 },
  recent_count: 4,
  baseline_count: 4,
  absolute_change: 0.1,
  percent_change: 0.1426,
  classification: "STABLE",
  confidence: "MODERATE",
  evidence: [],
  evidence_ids: [],
});

const insufficient = numericResult({
  metric: "activity_duration",
  metric_label: "Activity duration per logged entry",
  context: null,
  unit: "min",
  recent_count: 1,
  baseline_count: 4,
  recent_summary: { count: 1, mean: 45, median: 45, minimum: 45, maximum: 45, standard_deviation: 0, first_value: 45, last_value: 45 },
  absolute_change: null,
  percent_change: null,
  classification: "INSUFFICIENT_DATA",
  confidence: "INSUFFICIENT",
  missing_data: ["Only 1 recent reading(s) are available; at least 2 are required."],
  evidence: [],
  evidence_ids: [],
});

const symptom: SymptomFrequencyResult = {
  profile_id: profile.id,
  symptom_name: "Constipation",
  reference_date: "2026-09-13",
  recent_period: { start: "2026-08-15", end: "2026-09-13", days: 30, boundaries: "inclusive" },
  baseline_period: { start: "2026-05-17", end: "2026-08-14", days: 90, boundaries: "inclusive" },
  recent_count: 4,
  baseline_count: 2,
  recent_rate_per_day: 0.1333,
  baseline_rate_per_day: 0.0222,
  percent_change: 500,
  classification: "INCREASED",
  confidence: "LOW",
  confidence_reason: "Both periods contain reports, but the sample size is limited.",
  missing_data: [],
  evidence_ids: [],
  evidence: [],
  calculation_version: "symptom-frequency-v1",
  explanation: "Constipation was reported more frequently in the recent period.",
};

function renderPage() {
  return render(<ProfileProvider><InsightsPage /></ProfileProvider>);
}

beforeEach(() => {
  vi.mocked(getProfiles).mockResolvedValue([profile]);
  vi.mocked(getAvailableMetrics).mockResolvedValue({
    profile_id: profile.id,
    metrics: [
      { metric: "glucose", label: "Glucose", contexts: ["AFTER_MEAL"] },
      { metric: "weight", label: "Weight", contexts: [] },
      { metric: "activity_duration", label: "Activity duration per logged entry", contexts: [] },
    ],
    symptoms: ["Constipation"],
  });
  vi.mocked(getWhatChanged).mockResolvedValue({ profile_id: profile.id, results: [numericResult()] });
  vi.mocked(getTrend).mockImplementation(async (_profile, metric) => {
    if (metric === "weight") return stable;
    if (metric === "activity_duration") return insufficient;
    return numericResult();
  });
  vi.mocked(getSymptomFrequency).mockResolvedValue(symptom);
});

describe("Phase 9 Insights UI", () => {
  it("renders real What Changed data, personal baseline, and API-backed chart", async () => {
    renderPage();
    expect(await screen.findByText("Compared with your own recorded history")).toBeInTheDocument();
    expect((await screen.findAllByText("Increased")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("172 mg/dL").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("148 mg/dL").length).toBeGreaterThanOrEqual(1);
    expect(
      await screen.findByRole("img", { name: /time-series chart using 2 recorded values/i }),
    ).toBeInTheDocument();
    expect(getWhatChanged).toHaveBeenCalledWith(profile.id);
  });

  it("uses the metric selector and renders a stable result", async () => {
    renderPage();
    const selector = await screen.findByLabelText("Metric");
    await screen.findByRole("heading", { name: "Increased" });
    fireEvent.change(selector, { target: { value: "metric|weight|" } });
    await waitFor(() => expect(getTrend).toHaveBeenLastCalledWith(profile.id, "weight", null, expect.any(AbortSignal)));
    expect(await screen.findByRole("heading", { name: "Stable" })).toBeInTheDocument();
    expect(screen.getByText("70.25 kg")).toBeInTheDocument();
  });

  it("shows insufficient data and the exact missing count", async () => {
    renderPage();
    const selector = await screen.findByLabelText("Metric");
    await screen.findByRole("heading", { name: "Increased" });
    fireEvent.change(selector, { target: { value: "metric|activity_duration|" } });
    expect(await screen.findByText("Not enough data to compare.")).toBeInTheDocument();
    expect(screen.getByText("Recent readings: 1")).toBeInTheDocument();
    expect(screen.getByText(/at least 2 are required/i)).toBeInTheDocument();
  });

  it("opens WHY with periods, calculation, raw values, evidence, and confidence reasoning", async () => {
    renderPage();
    const buttons = await screen.findAllByRole("button", { name: "WHY?" });
    fireEvent.click(buttons.at(-1)!);
    expect(await screen.findByRole("complementary", { name: "Analytics calculation evidence" })).toBeInTheDocument();
    expect(screen.getByText("HOW IT WAS CALCULATED")).toBeInTheDocument();
    expect(screen.getByText("145 mg/dL")).toBeInTheDocument();
    expect(screen.getByText("168 mg/dL")).toBeInTheDocument();
    expect(screen.getByText("labs.txt, page 1 · Document Verified")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Source" })).toHaveAttribute("href", "/uploads?document=doc-1&page=1");
    expect(screen.getByText(/Minimum counts are met/i)).toBeInTheDocument();
  });

  it("loads symptom frequency without causal or diagnostic language", async () => {
    renderPage();
    const selector = await screen.findByLabelText("Metric");
    await screen.findByRole("heading", { name: "Increased" });
    fireEvent.change(selector, { target: { value: "symptom|Constipation" } });
    expect(await screen.findByRole("heading", { name: "Constipation: Increased" })).toBeInTheDocument();
    expect(screen.getByText("Constipation was reported more frequently in the recent period.")).toBeInTheDocument();
    expect(screen.getByText(/Unlogged days remain unknown/i)).toBeInTheDocument();
  });

  it("shows an API failure state", async () => {
    vi.mocked(getWhatChanged).mockRejectedValue(new Error("offline"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });
});
