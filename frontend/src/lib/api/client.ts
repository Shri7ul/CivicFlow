const DEFAULT_API_BASE_URL = "http://localhost:8000";

type ErrorPayload = {
  error?: {
    code?: string;
    message?: string;
  };
};

export type ApiRequestOptions = Omit<RequestInit, "signal"> & {
  timeoutMs?: number;
  signal?: AbortSignal;
};

export type UploadProgress = (percent: number) => void;

export class ApiError extends Error {
  readonly status?: number;
  readonly code?: string;

  constructor(
    message: string,
    options: { status?: number; code?: string } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
  }
}

export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return (configured || DEFAULT_API_BASE_URL).replace(/\/+$/, "");
}

function readJsonErrorPayload(payload: ErrorPayload, status: number): {
  message: string;
  code?: string;
} {
  return {
    message:
      payload.error?.message ??
      `The API responded with status ${status}.`,
    code: payload.error?.code,
  };
}

async function readErrorPayload(response: Response): Promise<{
  message: string;
  code?: string;
}> {
  try {
    const payload = (await response.json()) as ErrorPayload;
    return {
      message:
        payload.error?.message ??
        `The API responded with status ${response.status}.`,
      code: payload.error?.code,
    };
  } catch {
    return {
      message: `The API responded with status ${response.status}.`,
    };
  }
}

export async function apiFetch<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { timeoutMs = 8000, headers, signal, ...init } = options;
  const url = `${getApiBaseUrl()}/${path.replace(/^\/+/, "")}`;
  const requestHeaders = new Headers(headers);
  if (!requestHeaders.has("Accept")) {
    requestHeaders.set("Accept", "application/json");
  }

  const controller = new AbortController();
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const forwardAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", forwardAbort, { once: true });
    }
  }

  try {
    const response = await fetch(url, {
      ...init,
      headers: requestHeaders,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await readErrorPayload(response);
      throw new ApiError(error.message, {
        status: response.status,
        code: error.code ?? "api_error",
      });
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === "AbortError") {
      if (timedOut) {
        throw new ApiError(
          "The API request timed out. Check that the backend is running.",
          { code: "request_timeout" },
        );
      }
      throw new ApiError("The request was cancelled.", {
        code: "request_cancelled",
      });
    }
    throw new ApiError(
      "Unable to reach the CivicFlow API. Check that the backend is running.",
      { code: "network_error" },
    );
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", forwardAbort);
  }
}

export function uploadFormData<T>(
  path: string,
  formData: FormData,
  token: string,
  options: { timeoutMs?: number; onProgress?: UploadProgress } = {},
): Promise<T> {
  const { timeoutMs = 120000, onProgress } = options;
  const url = `${getApiBaseUrl()}/${path.replace(/^\/+/, "")}`;

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.timeout = timeoutMs;

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(
            new ApiError("The API returned an invalid response.", {
              status: xhr.status,
              code: "invalid_response",
            }),
          );
        }
        return;
      }
      let payload: ErrorPayload = {};
      try {
        payload = JSON.parse(xhr.responseText) as ErrorPayload;
      } catch {
        // Fall back to a status-only error below.
      }
      const parsed = readJsonErrorPayload(payload, xhr.status);
      reject(
        new ApiError(parsed.message, {
          status: xhr.status,
          code: parsed.code ?? "api_error",
        }),
      );
    };
    xhr.onerror = () => {
      reject(
        new ApiError(
          "Unable to reach the CivicFlow API. Check that the backend is running.",
          { code: "network_error" },
        ),
      );
    };
    xhr.ontimeout = () => {
      reject(
        new ApiError("The upload timed out. Please try again.", {
          code: "request_timeout",
        }),
      );
    };
    xhr.onabort = () => {
      reject(new ApiError("The request was cancelled.", { code: "request_cancelled" }));
    };
    xhr.send(formData);
  });
}
