import { describe, expect, it, vi } from "vitest";

import type { ApiRequester } from "@/lib/api/incidents";
import { getAIInsights, requestAITriage } from "@/lib/api/ai";

type Call = [string, { method?: string; body?: string } | undefined];

function recorder() {
  const request = vi.fn(async () => ({})) as unknown as ApiRequester;
  const calls = (request as unknown as { mock: { calls: Call[] } }).mock.calls;
  return { request, at: (index: number): Call => calls[index]! };
}

describe("Civic AI API contract", () => {
  it("reads local insights from the authenticated endpoint", async () => {
    const { request, at } = recorder();
    await getAIInsights(request);
    expect(at(0)[0]).toBe("/api/v1/ai/insights");
  });

  it("posts advisory triage input without applying anything", async () => {
    const { request, at } = recorder();
    await requestAITriage(request, "Flooded road", "Water is rising");
    expect(at(0)[0]).toBe("/api/v1/ai/triage");
    expect(at(0)[1]?.method).toBe("POST");
    expect(JSON.parse(at(0)[1]!.body!)).toEqual({
      title: "Flooded road",
      description: "Water is rising",
    });
  });
});
