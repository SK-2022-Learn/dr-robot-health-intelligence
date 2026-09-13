import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AgentResponse } from "@/components/chat/agent-response";
import type { AskResponse } from "@/lib/types/api";

vi.mock("next/link", () => ({
  default: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a {...props} />,
}));

const response: AskResponse = {
  request_id: "request-a",
  intent: "ANALYTICS_QUERY",
  answer: "Post-meal glucose increased in the recent period.",
  conversation_id: null,
  pending_id: null,
  clarification_required: false,
  sources: [{
    source_type: "CHAT",
    label: "User-reported source",
    evidence_path: "/api/v1/profiles/p/evidence/observation/o",
    entity_type: "observation",
    entity_id: "o",
    document_id: null,
    page_number: null,
  }],
  evidence: [],
  safety: null,
  warnings: [],
  actions: ["deterministic_analytics", "analytics_evidence_attached"],
  structured_result: {
    metric_label: "Glucose",
    classification: "INCREASED",
    recent_summary: { mean: 172 },
    baseline_summary: { mean: 148 },
  },
  nodes_run: ["safety_pre", "router", "analytics", "evidence", "safety_post"],
};

describe("agent response", () => {
  it("renders structured analytics, source links, and inspectable operation labels", () => {
    render(<AgentResponse response={response} />);

    expect(screen.getByText("Analytics Query")).toBeInTheDocument();
    expect(screen.getByText("172")).toBeInTheDocument();
    expect(screen.getByText("148")).toBeInTheDocument();
    expect(screen.getByText("WHY / sources")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "User-reported source" })).toHaveAttribute(
      "href",
      "http://localhost:8000/api/v1/profiles/p/evidence/observation/o",
    );
    expect(screen.getByText(/Deterministic Analytics/)).toBeInTheDocument();
  });
});
