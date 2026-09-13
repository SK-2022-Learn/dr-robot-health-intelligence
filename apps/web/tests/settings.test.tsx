import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/settings/page";
import { getAuditLogs } from "@/lib/api/audit";
import { getSystemStatus } from "@/lib/api/system";
import type { AuditLog, SystemStatus } from "@/lib/types/api";

vi.mock("@/lib/api/audit", () => ({ getAuditLogs: vi.fn() }));
vi.mock("@/lib/api/system", () => ({ getSystemStatus: vi.fn() }));

function auditEntry(id: string, action: string, entityType: string, createdAt: string): AuditLog {
  return {
    id,
    actor_user_id: "owner",
    action,
    entity_type: entityType,
    entity_id: `entity-${id}`,
    before_state: null,
    after_state: null,
    created_at: createdAt,
  };
}

beforeEach(() => {
  vi.mocked(getSystemStatus).mockReturnValue(new Promise(() => undefined));
});

describe("Settings audit activity", () => {
  it("groups matching events from the same day without discarding the audit history", async () => {
    vi.mocked(getAuditLogs).mockResolvedValue([
      auditEntry("3", "DOCTOR_VISIT_BRIEF_GENERATED", "DOCTOR_VISIT_BRIEF", "2026-09-13T18:03:00Z"),
      auditEntry("2", "DOCTOR_VISIT_BRIEF_GENERATED", "DOCTOR_VISIT_BRIEF", "2026-09-13T18:02:00Z"),
      auditEntry("1", "DOCTOR_VISIT_BRIEF_GENERATED", "DOCTOR_VISIT_BRIEF", "2026-09-13T18:01:00Z"),
      auditEntry("4", "DOCUMENT_INDEXING_COMPLETED", "SOURCE_DOCUMENT", "2026-09-13T17:00:00Z"),
    ]);

    render(<SettingsPage />);

    expect(await screen.findByText("3 occurrences")).toBeInTheDocument();
    expect(screen.getAllByText("Doctor Visit Brief Generated")).toHaveLength(1);
    expect(screen.getByText("Document Indexing Completed")).toBeInTheDocument();
    expect(getAuditLogs).toHaveBeenCalledOnce();
  });

  it("shows every final v1 subsystem without exposing credentials", async () => {
    const status: SystemStatus = {
      environment: "development",
      database: "connected",
      upload_directory: "configured",
      vector_provider: "Pinecone",
      vector_status: "connected",
      vector_index: "test-index",
      vector_dimension: 768,
      vector_metric: "cosine",
      vector_count: 3,
      embedding_provider: "Ollama",
      embedding_model: "test-embedding",
      embedding_status: "connected",
      embedding_dimension: 768,
      compatibility: "compatible",
      llm_provider: "Ollama",
      llm_model: "test-model",
      llm: "connected",
      safety_policy: "enabled",
      safety_policy_version: "safety-v1",
      agent_orchestration: "enabled",
    };
    vi.mocked(getSystemStatus).mockResolvedValue(status);
    vi.mocked(getAuditLogs).mockResolvedValue([]);

    render(<SettingsPage />);

    expect(await screen.findByText("SQLite")).toBeInTheDocument();
    expect(screen.getByText("Pinecone")).toBeInTheDocument();
    expect(screen.getAllByText("Ollama")).toHaveLength(2);
    expect(screen.getByText("Safety Gate")).toBeInTheDocument();
    expect(screen.getByText("Agent Orchestration")).toBeInTheDocument();
    expect(screen.queryByText(/api.?key/i)).not.toBeInTheDocument();
  });
});
