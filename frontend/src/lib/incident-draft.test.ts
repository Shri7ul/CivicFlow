import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearIncidentDraft,
  INCIDENT_DRAFT_KEY,
  readIncidentDraft,
  writeIncidentDraft,
} from "@/lib/incident-draft";

const storage = new Map<string, string>();

beforeEach(() => {
  storage.clear();
  vi.stubGlobal("window", {
    sessionStorage: {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => void storage.set(key, value),
      removeItem: (key: string) => void storage.delete(key),
    },
  });
});

describe("incident report draft", () => {
  it("round-trips every form field", () => {
    const draft = {
      title: "Blocked drain",
      description: "Water is pooling beside the school gate.",
      category: "DRAINAGE" as const,
      severity: "HIGH" as const,
      latitude: "23.812000",
      longitude: "90.414000",
      address: "Road 12",
    };
    writeIncidentDraft(draft);
    expect(readIncidentDraft()).toEqual(draft);
  });

  it("ignores malformed stored data", () => {
    storage.set(INCIDENT_DRAFT_KEY, "{not json");
    expect(readIncidentDraft()).toEqual({});
  });

  it("clears only its own key after submission", () => {
    storage.set("unrelated", "keep");
    writeIncidentDraft({
      title: "Done",
      description: "Submitted report",
      category: "ROADS",
      severity: "LOW",
      latitude: "23.8",
      longitude: "90.4",
      address: "",
    });
    clearIncidentDraft();
    expect(storage.has(INCIDENT_DRAFT_KEY)).toBe(false);
    expect(storage.get("unrelated")).toBe("keep");
  });
});
