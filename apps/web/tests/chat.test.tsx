import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatPage from "@/app/chat/page";
import { StructuredPreview } from "@/components/chat/structured-preview";
import { ProfileProvider } from "@/components/health/profile-context";
import { askDrRobot } from "@/lib/api/agents";
import {
  clarifyPending,
  confirmPending,
  correctPending,
  createConversation,
  getConversation,
  getConversations,
  rejectPending,
} from "@/lib/api/chat";
import { getProfiles } from "@/lib/api/profiles";
import type {
  AgentIntent,
  AskResponse,
  ConversationDetail,
  DailyHealthExtraction,
  PendingHealthEntry,
  Profile,
  SafetyCategory,
  SafetyDecision,
  SafetyResult,
} from "@/lib/types/api";

vi.mock("next/link", () => ({ default: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a {...props} /> }));
vi.mock("@/lib/api/profiles", () => ({ getProfiles: vi.fn() }));
vi.mock("@/lib/api/agents", () => ({ askDrRobot: vi.fn() }));
vi.mock("@/lib/api/chat", () => ({
  clarifyPending: vi.fn(),
  confirmPending: vi.fn(),
  correctPending: vi.fn(),
  createConversation: vi.fn(),
  getConversation: vi.fn(),
  getConversations: vi.fn(),
  rejectPending: vi.fn(),
}));

const profile: Profile = {
  id: "profile-a",
  owner_user_id: "owner",
  display_name: "Lakshmi",
  relationship_to_owner: "SELF",
  date_of_birth: null,
  sex: null,
  access_level: "PRIVATE",
  is_active: true,
  created_at: "2026-09-13T00:00:00Z",
  updated_at: "2026-09-13T00:00:00Z",
};
const conversation = {
  id: "conversation-a",
  profile_id: profile.id,
  title: "Daily health log",
  created_at: "2026-09-13T00:00:00Z",
  updated_at: "2026-09-13T00:00:00Z",
};
const detail: ConversationDetail = { ...conversation, messages: [], pending_entries: [] };

function baseExtraction(): DailyHealthExtraction {
  return {
    observations: [],
    symptoms: [],
    activities: [],
    sleep_entries: [],
    clarifications: [],
    warnings: [],
  };
}

function pending(extraction: DailyHealthExtraction): PendingHealthEntry {
  return {
    id: "pending-a",
    conversation_id: conversation.id,
    message_id: "message-a",
    profile_id: profile.id,
    extraction,
    status: "PENDING_REVIEW",
    was_corrected: false,
    trusted_records: [],
    created_at: "2026-09-13T00:00:00Z",
    updated_at: "2026-09-13T00:00:00Z",
  };
}

function safety(decision: SafetyDecision, category: SafetyCategory): SafetyResult {
  return {
    decision,
    category,
    rule_id: `SAFE-${category}`,
    message: "Safety policy response.",
    safe_response_override: "Safety policy response.",
    requires_professional_evaluation: decision !== "ALLOW",
    emergency_guidance: decision === "ESCALATE",
    audit_metadata: { evaluation_stage: "PRE" },
    policy_version: "safety-v1",
  };
}

function agentResponse(
  answer: string,
  intent: AgentIntent,
  options: Partial<AskResponse> = {},
): AskResponse {
  return {
    request_id: "request-a",
    intent,
    answer,
    conversation_id: conversation.id,
    pending_id: null,
    clarification_required: false,
    sources: [],
    evidence: [],
    safety: safety("ALLOW", "GENERAL_HEALTH_INFORMATION"),
    warnings: [],
    actions: [],
    structured_result: null,
    nodes_run: ["safety_pre", "router", "explanation", "safety_post"],
    ...options,
  };
}

beforeEach(() => {
  vi.mocked(getProfiles).mockResolvedValue([profile]);
  vi.mocked(getConversations).mockResolvedValue([conversation]);
  vi.mocked(createConversation).mockResolvedValue(conversation);
  vi.mocked(getConversation).mockResolvedValue(detail);
});

describe("daily chat", () => {
  it("shows a multi-fact structured preview and confirms only on request", async () => {
    const extraction: DailyHealthExtraction = {
      observations: [
        { entry_type: "glucose", value: 118, unit: "mg/dL", context: "FASTING", observed_at: null, confidence: 0.98 },
        { entry_type: "glucose", value: 172, unit: "mg/dL", context: "AFTER_MEAL", observed_at: null, confidence: 0.96 },
      ],
      sleep_entries: [{ duration_minutes: 360, sleep_date: null, quality: null, confidence: 0.95 }],
      symptoms: [{ name: "Constipation", severity: "MILD", started_at: null, duration_text: null, notes: null, confidence: 0.9 }],
      activities: [{ activity_type: "walking", duration_minutes: 25, distance: null, distance_unit: null, observed_at: null, confidence: 0.94 }],
      clarifications: [],
      warnings: [],
    };
    const daily = {
      message_id: "message-a",
      pending_id: "pending-a",
      status: "STRUCTURED_PREVIEW",
      extraction,
      questions: [],
      assistant_message: "Here is what I understood.",
    };
    vi.mocked(askDrRobot).mockResolvedValue(agentResponse(
      daily.assistant_message,
      "DAILY_LOG",
      {
        pending_id: "pending-a",
        structured_result: { kind: "daily_log", response: daily },
      },
    ));
    vi.mocked(confirmPending).mockResolvedValue({
      pending: { ...pending(extraction), status: "CONFIRMED" },
      trusted_records: [{ record_type: "observations", record_id: "observation-a" }],
      already_confirmed: false,
    });
    render(<ProfileProvider><ChatPage /></ProfileProvider>);
    const composer = await screen.findByLabelText("Ask or share a daily health update");
    fireEvent.change(composer, { target: { value: "Morning sugar 118 before food. After breakfast 172. Slept 6 hours. Little constipation. Walked 25 minutes." } });
    fireEvent.click(screen.getByRole("button", { name: "Ask Dr. Robot" }));

    expect(await screen.findByRole("heading", { name: "Here is what I understood" })).toBeInTheDocument();
    expect(screen.getByText("118 mg/dL")).toBeInTheDocument();
    expect(screen.getByText("172 mg/dL")).toBeInTheDocument();
    expect(screen.getByText("6 hours")).toBeInTheDocument();
    expect(screen.getByText("Symptom: Constipation")).toBeInTheDocument();
    expect(screen.getByText("25 minutes")).toBeInTheDocument();
    expect(confirmPending).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("Saved to your health memory.")).toBeInTheDocument();
    expect(confirmPending).toHaveBeenCalledWith("pending-a");
  });

  it("asks glucose and weight clarification without guessing", async () => {
    const glucoseExtraction = baseExtraction();
    glucoseExtraction.observations = [
      { entry_type: "glucose", value: 165, unit: "mg/dL", context: "UNKNOWN", observed_at: null, confidence: 0.9 },
    ];
    const glucoseQuestion = {
      field: "observations.0.context",
      question: "Was this reading fasting, before a meal, after a meal, or random?",
      options: ["FASTING", "BEFORE_MEAL", "AFTER_MEAL", "RANDOM"],
    };
    glucoseExtraction.clarifications = [glucoseQuestion];
    const clarified = structuredClone(glucoseExtraction);
    clarified.observations[0] = {
      entry_type: "glucose",
      value: 165,
      unit: "mg/dL",
      context: "FASTING",
      observed_at: null,
      confidence: 0.9,
    };
    clarified.clarifications = [];
    vi.mocked(clarifyPending).mockResolvedValue({
      message_id: "message-a",
      pending_id: "pending-a",
      status: "STRUCTURED_PREVIEW",
      extraction: clarified,
      questions: [],
      assistant_message: "Updated preview.",
    });
    const view = render(
      <StructuredPreview pendingId="pending-a" initial={glucoseExtraction} questions={[glucoseQuestion]} onChanged={vi.fn()} />,
    );
    expect(screen.getByText(glucoseQuestion.question)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Fasting" }));
    expect(await screen.findByRole("heading", { name: "Here is what I understood" })).toBeInTheDocument();
    expect(clarifyPending).toHaveBeenCalledWith("pending-a", { "observations.0.context": "FASTING" });

    view.unmount();
    const weightExtraction = baseExtraction();
    weightExtraction.observations = [
      { entry_type: "weight", value: 72, unit: null, observed_at: null, confidence: 0.9 },
    ];
    const weightQuestion = { field: "observations.0.unit", question: "Is that 72 kg or 72 lb?", options: ["kg", "lb"] };
    render(<StructuredPreview pendingId="pending-b" initial={weightExtraction} questions={[weightQuestion]} onChanged={vi.fn()} />);
    expect(screen.getByText("Is that 72 kg or 72 lb?")).toBeInTheDocument();
  });

  it("sends corrected values to the backend and can discard without confirming", async () => {
    const extraction = baseExtraction();
    extraction.observations = [
      { entry_type: "glucose", value: 181, unit: "mg/dL", context: "FASTING", observed_at: null, confidence: 0.96 },
    ];
    const corrected = structuredClone(extraction);
    corrected.observations[0] = {
      entry_type: "glucose",
      value: 118,
      unit: "mg/dL",
      context: "FASTING",
      observed_at: null,
      confidence: 0.96,
    };
    vi.mocked(correctPending).mockResolvedValue({ ...pending(corrected), was_corrected: true });
    vi.mocked(rejectPending).mockResolvedValue({ ...pending(corrected), status: "REJECTED" });
    const changed = vi.fn();
    render(<StructuredPreview pendingId="pending-a" initial={extraction} questions={[]} onChanged={changed} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Fasting glucose value"), { target: { value: "118" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(correctPending).toHaveBeenCalled());
    expect(vi.mocked(correctPending).mock.calls[0][1].observations[0]).toMatchObject({ value: 118 });

    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(await screen.findByText(/nothing was added to health memory/i)).toBeInTheDocument();
    expect(rejectPending).toHaveBeenCalledWith("pending-a");
  });

  it.each([
    ["I have severe chest pain and I can't breathe.", "ESCALATE", "URGENT_SYMPTOM", "Call emergency services now."],
    ["Should I stop metformin?", "BLOCK", "MEDICATION_CHANGE", "Do not change prescribed medication."],
    ["Do I have diabetes?", "WARN", "DIAGNOSIS_REQUEST", "I can't diagnose a condition."],
    ["Turmeric cures diabetes.", "BLOCK", "UNSUPPORTED_CURE_CLAIM", "Unsupported cure claims are blocked."],
  ] as const)("renders a distinct safety state for %s", async (input, decision, category, message) => {
    vi.mocked(askDrRobot).mockResolvedValue(agentResponse(message, "UNKNOWN", {
      safety: safety(decision, category),
      conversation_id: null,
      actions: ["safety_short_circuit"],
      nodes_run: ["safety_pre"],
    }));
    render(<ProfileProvider><ChatPage /></ProfileProvider>);
    const composer = await screen.findByLabelText("Ask or share a daily health update");
    fireEvent.change(composer, { target: { value: input } });
    fireEvent.click(screen.getByRole("button", { name: "Ask Dr. Robot" }));

    const region = decision === "ESCALATE" ? await screen.findByRole("alert") : await screen.findByRole("status");
    expect(region).toHaveTextContent(message);
    expect(screen.getByText(
      decision === "ESCALATE" ? "Urgent" : decision === "BLOCK" ? "Safety boundary" : "Checked",
    )).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Here is what I understood" })).not.toBeInTheDocument();
  });

  it("renders safe informational output as a normal health-information response", async () => {
    vi.mocked(askDrRobot).mockResolvedValue(agentResponse(
      "HbA1c reflects average blood glucose over roughly two to three months.",
      "GENERAL_HEALTH_INFORMATION",
    ));
    render(<ProfileProvider><ChatPage /></ProfileProvider>);
    const composer = await screen.findByLabelText("Ask or share a daily health update");
    fireEvent.change(composer, { target: { value: "What does HbA1c measure?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask Dr. Robot" }));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("HbA1c reflects average blood glucose");
    expect(screen.getByText("General Health Information")).toBeInTheDocument();
  });

  it("does not render historical reporting as an urgent or medication boundary", async () => {
    const historicalExtraction = baseExtraction();
    const historical = {
      message_id: "message-a",
      pending_id: "pending-a",
      status: "STRUCTURED_PREVIEW",
      extraction: historicalExtraction,
      questions: [],
      assistant_message: "Here is what I understood.",
      safety: safety("ALLOW", "LOGGING_ONLY"),
    };
    vi.mocked(askDrRobot).mockResolvedValue(agentResponse(
      historical.assistant_message,
      "DAILY_LOG",
      {
        pending_id: "pending-a",
        structured_result: { kind: "daily_log", response: historical },
      },
    ));
    render(<ProfileProvider><ChatPage /></ProfileProvider>);
    const composer = await screen.findByLabelText("Ask or share a daily health update");
    fireEvent.change(composer, { target: { value: "My doctor told me to stop metformin last year." } });
    fireEvent.click(screen.getByRole("button", { name: "Ask Dr. Robot" }));

    expect(await screen.findByRole("heading", { name: "Here is what I understood" })).toBeInTheDocument();
    expect(screen.queryByText("Medication boundary")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
