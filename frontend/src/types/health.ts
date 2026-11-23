export type BackendHealth = {
  status: "healthy";
  service: string;
  environment: string;
  version: string;
};

export type BackendHealthStatus = "loading" | "healthy" | "error";

export type BackendHealthState = {
  status: BackendHealthStatus;
  data: BackendHealth | null;
  error: string | null;
  checkedAt: string | null;
};
