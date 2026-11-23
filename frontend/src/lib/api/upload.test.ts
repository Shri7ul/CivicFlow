import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { uploadFormData } from "@/lib/api/client";

class FakeXhr {
  static last: FakeXhr | null = null;
  static nextStatus = 201;
  static nextResponse = "[]";
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = {
    onprogress: null,
  };
  status = 201;
  responseText = "[]";
  timeout = 0;
  url = "";
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  headers: Record<string, string> = {};
  body: FormData | null = null;

  constructor() {
    FakeXhr.last = this;
    this.status = FakeXhr.nextStatus;
    this.responseText = FakeXhr.nextResponse;
  }

  open(_method: string, url: string) {
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  send(body: FormData) {
    this.body = body;
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded: 50,
      total: 100,
    } as ProgressEvent);
    queueMicrotask(() => this.onload?.());
  }
}

describe("uploadFormData", () => {
  beforeEach(() => {
    FakeXhr.last = null;
    FakeXhr.nextStatus = 201;
    FakeXhr.nextResponse = "[]";
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the bearer token outside the URL and reports progress", async () => {
    const body = new FormData();
    body.append("files", new File(["x"], "x.png", { type: "image/png" }));
    const progress: number[] = [];

    await uploadFormData("/api/v1/incidents/1/evidence", body, "secret-token", {
      onProgress: (value) => progress.push(value),
    });

    expect(FakeXhr.last?.url).toContain("/api/v1/incidents/1/evidence");
    expect(FakeXhr.last?.url).not.toContain("secret-token");
    expect(FakeXhr.last?.headers.Authorization).toBe("Bearer secret-token");
    expect(progress).toEqual([50]);
  });

  it("preserves structured upload errors", async () => {
    FakeXhr.nextStatus = 413;
    FakeXhr.nextResponse = JSON.stringify({
      error: { code: "evidence_too_large", message: "Too large." },
    });

    await expect(
      uploadFormData("/api/v1/evidence", new FormData(), "token"),
    ).rejects.toMatchObject({
      status: 413,
      code: "evidence_too_large",
    });
  });
});
