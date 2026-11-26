import { describe, expect, it, vi } from "vitest";

import type { ApiRequester } from "@/lib/api/incidents";
import {
  assignIncident,
  getAdminOverview,
  getMyApplication,
  getMyWorkerProfile,
  listAssignments,
  listAuditEvents,
  listCandidates,
  listNotifications,
  listWorkerApplications,
  listWorkers,
  markNotificationRead,
  recordProgress,
  reviewWorkerApplication,
  setWorkerStatus,
  submitCompletion,
  submitWorkerApplication,
  verifyCompletion,
} from "@/lib/api/workforce";
import type { ApplicationPayload } from "@/types/workforce";

type Call = [string, { method?: string; body?: string } | undefined];

function recorder() {
  const request = vi.fn(async () => ({})) as unknown as ApiRequester;
  const calls = (request as unknown as { mock: { calls: Call[] } }).mock.calls;
  const at = (index: number): Call => calls[index]!;
  return { request, calls, at };
}

const application: ApplicationPayload = {
  full_name: "Field Worker",
  specialization: "Water supply",
  service_area: "Ward 12",
};

describe("workforce API contract", () => {
  it("submits an application and reads the caller's records", async () => {
    const { request, at } = recorder();
    await submitWorkerApplication(request, application);
    await getMyApplication(request);
    await getMyWorkerProfile(request);
    expect(at(0)[0]).toBe("/api/v1/workforce/applications");
    expect(at(0)[1]?.method).toBe("POST");
    expect(JSON.parse(at(0)[1]!.body!)).toEqual(application);
    expect(at(1)[0]).toBe("/api/v1/workforce/applications/mine");
    expect(at(2)[0]).toBe("/api/v1/workforce/workers/me");
  });

  it("encodes list filters and omits empty values", async () => {
    const { request, at } = recorder();
    await listWorkerApplications(request, { status: "PENDING", limit: 25 });
    await listWorkers(request, { status: "ACTIVE" });
    await listAssignments(request, { status: "IN_PROGRESS", offset: 10 });
    await listAuditEvents(request, "worker_application");
    expect(at(0)[0]).toBe(
      "/api/v1/workforce/applications?status=PENDING&limit=25",
    );
    expect(at(1)[0]).toBe("/api/v1/workforce/workers?status=ACTIVE");
    expect(at(2)[0]).toBe(
      "/api/v1/workforce/assignments?status=IN_PROGRESS&offset=10",
    );
    expect(at(3)[0]).toBe(
      "/api/v1/workforce/events?entity_type=worker_application&limit=100",
    );
  });

  it("sends the review decision and required note", async () => {
    const { request, at } = recorder();
    await reviewWorkerApplication(request, "app-1", "REJECT", "Incomplete credentials");
    expect(at(0)[0]).toBe("/api/v1/workforce/applications/app-1/review");
    expect(JSON.parse(at(0)[1]!.body!)).toEqual({
      decision: "REJECT",
      note: "Incomplete credentials",
    });
  });

  it("suspends with a reason and reactivates without a body", async () => {
    const { request, at } = recorder();
    await setWorkerStatus(request, "worker-1", "suspend", "Under investigation");
    await setWorkerStatus(request, "worker-1", "reactivate");
    expect(at(0)[0]).toBe("/api/v1/workforce/workers/worker-1/suspend");
    expect(JSON.parse(at(0)[1]!.body!)).toEqual({ note: "Under investigation" });
    expect(at(1)[0]).toBe("/api/v1/workforce/workers/worker-1/reactivate");
    expect(at(1)[1]?.body).toBeUndefined();
  });

  it("uses deterministic assignment candidate and create contracts", async () => {
    const { request, at } = recorder();
    await listCandidates(request, "incident-1");
    await assignIncident(request, {
      incidentId: "incident-1",
      workerProfileId: "worker-1",
      note: "Nearest available",
    });
    expect(at(0)[0]).toBe(
      "/api/v1/workforce/assignments/candidates?incident_id=incident-1",
    );
    expect(at(1)[0]).toBe("/api/v1/workforce/assignments");
    expect(JSON.parse(at(1)[1]!.body!)).toEqual({
      incident_id: "incident-1",
      worker_profile_id: "worker-1",
      note: "Nearest available",
    });
  });

  it("sends progress, completion, and verification payloads", async () => {
    const { request, at } = recorder();
    await recordProgress(request, "assignment-1", "Excavating", 45);
    await submitCompletion(request, "assignment-1", "Repair finished", "Photo attached");
    await verifyCompletion(request, "assignment-1", true, "Verified on site");
    expect(at(0)[0]).toBe("/api/v1/workforce/assignments/assignment-1/progress");
    expect(JSON.parse(at(0)[1]!.body!)).toEqual({
      note: "Excavating",
      progress_percent: 45,
    });
    expect(at(1)[0]).toBe("/api/v1/workforce/assignments/assignment-1/complete");
    expect(JSON.parse(at(1)[1]!.body!)).toEqual({
      note: "Repair finished",
      evidence_note: "Photo attached",
    });
    expect(at(2)[0]).toBe("/api/v1/workforce/assignments/assignment-1/verify");
    expect(JSON.parse(at(2)[1]!.body!)).toEqual({
      approve: true,
      note: "Verified on site",
    });
  });

  it("reads overview and notifications and marks one read", async () => {
    const { request, at } = recorder();
    await getAdminOverview(request);
    await listNotifications(request);
    await markNotificationRead(request, "notice-1");
    expect(at(0)[0]).toBe("/api/v1/workforce/admin/overview");
    expect(at(1)[0]).toBe("/api/v1/workforce/notifications");
    expect(at(2)[0]).toBe("/api/v1/workforce/notifications/notice-1/read");
    expect(at(2)[1]?.method).toBe("POST");
  });
});
