import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiMutation } from "@/lib/api/client";
import { generateDoctorVisitBrief } from "@/lib/api/doctor-visit";
import type { DoctorVisitBrief } from "@/lib/types/api";

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiMutation: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(apiMutation).mockReset();
});

describe("Doctor Visit Brief API", () => {
  it("shares a request already in flight for the same profile", async () => {
    let resolveRequest: (brief: DoctorVisitBrief) => void = () => undefined;
    const pending = new Promise<DoctorVisitBrief>((resolve) => {
      resolveRequest = resolve;
    });
    const brief = { profile_id: "profile-1" } as DoctorVisitBrief;
    vi.mocked(apiMutation).mockReturnValue(pending);

    const first = generateDoctorVisitBrief("profile-1");
    const second = generateDoctorVisitBrief("profile-1");

    expect(second).toBe(first);
    expect(apiMutation).toHaveBeenCalledOnce();

    resolveRequest(brief);
    await expect(first).resolves.toBe(brief);

    vi.mocked(apiMutation).mockResolvedValue(brief);
    await generateDoctorVisitBrief("profile-1");
    expect(apiMutation).toHaveBeenCalledTimes(2);
  });
});
