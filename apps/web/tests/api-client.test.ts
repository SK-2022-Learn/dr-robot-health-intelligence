import { afterEach, describe, expect, it, vi } from "vitest";

import { apiGet, ApiClientError, isRecord } from "@/lib/api/client";
import { getSystemStatus } from "@/lib/api/system";

const isNamedPayload = (value: unknown): value is { name: string } =>
  isRecord(value) && typeof value.name === "string";

afterEach(() => vi.unstubAllGlobals());

describe("typed API client", () => {
  it("returns a validated successful response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"name":"ok"}')));
    await expect(apiGet("/test", isNamedPayload)).resolves.toEqual({ name: "ok" });
  });

  it("preserves a non-2xx API error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"error":{"code":"NOT_FOUND","message":"Missing record"}}', {
          status: 404,
        }),
      ),
    );
    await expect(apiGet("/test", isNamedPayload)).rejects.toMatchObject({
      code: "NOT_FOUND",
      message: "Missing record",
      status: 404,
    });
  });

  it("rejects unreadable JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not-json")));
    await expect(apiGet("/test", isNamedPayload)).rejects.toMatchObject({
      code: "MALFORMED_RESPONSE",
    });
  });

  it("rejects an unexpected successful response shape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"other":true}')));
    await expect(apiGet("/test", isNamedPayload)).rejects.toBeInstanceOf(ApiClientError);
  });

  it("maps network failure to a readable unavailable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network failed")));
    await expect(apiGet("/test", isNamedPayload)).rejects.toMatchObject({
      code: "API_UNAVAILABLE",
      status: null,
    });
  });

  it("allows infrastructure status checks enough time for bounded provider probes", async () => {
    const timeout = vi.spyOn(AbortSignal, "timeout");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({
          environment: "development",
          database: "connected",
          upload_directory: "configured",
          vector_provider: "Pinecone",
          vector_status: "connected",
          vector_index: "dr-robot",
          vector_dimension: 768,
          vector_metric: "cosine",
          vector_count: 10,
          embedding_provider: "Ollama",
          embedding_model: "nomic-embed-text:latest",
          embedding_status: "connected",
          embedding_dimension: 768,
          compatibility: "compatible",
          llm_provider: "Ollama",
          llm_model: "qwen3:8b",
          llm: "connected",
          safety_policy: "enabled",
          safety_policy_version: "safety-v1",
          agent_orchestration: "enabled",
        })),
      ),
    );

    await expect(getSystemStatus()).resolves.toMatchObject({ database: "connected" });
    expect(timeout).toHaveBeenCalledWith(15_000);
  });
});
