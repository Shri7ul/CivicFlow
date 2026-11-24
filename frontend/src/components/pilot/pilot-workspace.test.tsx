import { describe, expect, it } from "vitest";

import { normalizePilot } from "./pilot-workspace";
import type { Pilot } from "@/types/pilot";

describe("pilot list normalization", () => {
  it("defaults detail-only collections so a list summary cannot crash the workspace", () => {
    const summary = {
      id: "pilot-1",
      pilot_key: "pilot-1",
      name: "Summary pilot",
      description: "List payload without detail collections.",
      status: "APPROVED",
      mode: "SIMULATION",
      region: "Test region",
      bbox: [40.5, -74.1, 40.8, -73.8],
      start_date: "2026-11-01T00:00:00+00:00",
      end_date: "2026-12-01T00:00:00+00:00",
      eligible_categories: ["DRAINAGE"],
      evaluation_protocol: "Test protocol",
      operational_restrictions: ["No dispatch"],
      data_sources: ["Fixture"],
      evaluation_criteria: ["Review"],
      owner_id: "admin-1",
      created_by: "admin-1",
      approved_by: "admin-2",
      approved_at: "2026-11-01T00:00:00+00:00",
      activated_by: null,
      activated_at: null,
      paused_at: null,
      paused_by: null,
      pause_reason: null,
      completed_at: null,
      archived_at: null,
      rejection_reason: null,
      activation_readiness: {},
      reviewer_count: 0,
      created_at: "2026-11-01T00:00:00+00:00",
      updated_at: "2026-11-01T00:00:00+00:00",
      disclaimer: "Not an operational order.",
    } as unknown as Pilot;
    const normalized = normalizePilot(summary);
    expect(normalized.reviewers).toEqual([]);
    expect(normalized.history).toEqual([]);
    expect(normalized.allowed_actions).toEqual([]);
  });
});
