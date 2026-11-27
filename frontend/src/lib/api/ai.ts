import type { ApiRequester } from "@/lib/api/incidents";

export type AIInsights = {
  available: boolean;
  source: "groq" | "deterministic" | string;
  summary: string;
  highlights: string[];
  limitations: string;
  generated_at: string;
  incident_count: number;
  model: string | null;
};

export type AITriage = {
  available: boolean;
  source: string;
  suggested_category: string | null;
  suggested_severity: string | null;
  rationale: string;
  limitations: string;
  model: string | null;
};

export function getAIInsights(request: ApiRequester): Promise<AIInsights> {
  return request("/api/v1/ai/insights");
}

export function requestAITriage(
  request: ApiRequester,
  title: string,
  description: string,
): Promise<AITriage> {
  return request("/api/v1/ai/triage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description }),
  });
}
