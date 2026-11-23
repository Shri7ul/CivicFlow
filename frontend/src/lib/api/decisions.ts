import type { ApiRequestOptions } from "@/lib/api/client";
import type { ApiRequester } from "@/lib/api/incidents";
import type {
  ActionCreateInput,
  ComparisonResponse,
  DecisionConfig,
  DecisionStrategy,
  ResourceCreateInput,
  ResponseResource,
  ScenarioCreateInput,
  ScenarioDetail,
  ScenarioSummary,
  SimulationListItem,
  SimulationResponse,
} from "@/types/decisions";

const JSON_HEADERS = { "Content-Type": "application/json" };

export function getDecisionConfig(request: ApiRequester): Promise<DecisionConfig> {
  return request<DecisionConfig>("/api/v1/decisions/config");
}

export function listResponseResources(
  request: ApiRequester,
): Promise<ResponseResource[]> {
  return request<ResponseResource[]>("/api/v1/decisions/resources");
}

export function createResponseResource(
  request: ApiRequester,
  input: ResourceCreateInput,
): Promise<ResponseResource> {
  return request<ResponseResource>("/api/v1/decisions/resources", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

export function listDecisionScenarios(
  request: ApiRequester,
): Promise<ScenarioSummary[]> {
  return request<ScenarioSummary[]>("/api/v1/decisions/scenarios");
}

export function createDecisionScenario(
  request: ApiRequester,
  input: ScenarioCreateInput,
): Promise<ScenarioDetail> {
  return request<ScenarioDetail>("/api/v1/decisions/scenarios", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

export function getDecisionScenario(
  request: ApiRequester,
  scenarioId: string,
): Promise<ScenarioDetail> {
  return request<ScenarioDetail>(
    `/api/v1/decisions/scenarios/${encodeURIComponent(scenarioId)}`,
  );
}

export function createDecisionAction(
  request: ApiRequester,
  scenarioId: string,
  input: ActionCreateInput,
): Promise<unknown> {
  return request(`/api/v1/decisions/scenarios/${encodeURIComponent(scenarioId)}/actions`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

export function simulateDecisionScenario(
  request: ApiRequester,
  scenarioId: string,
  strategy: DecisionStrategy,
  options: Pick<ApiRequestOptions, "signal"> = {},
): Promise<SimulationResponse> {
  return request<SimulationResponse>(
    `/api/v1/decisions/scenarios/${encodeURIComponent(scenarioId)}/simulate`,
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ strategy, persist: true }),
      signal: options.signal,
    },
  );
}

export function compareDecisionStrategies(
  request: ApiRequester,
  scenarioId: string,
  strategies: DecisionStrategy[],
): Promise<ComparisonResponse> {
  return request<ComparisonResponse>(
    `/api/v1/decisions/scenarios/${encodeURIComponent(scenarioId)}/compare`,
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ strategies }),
    },
  );
}

export function listDecisionSimulations(
  request: ApiRequester,
  scenarioId: string,
): Promise<SimulationListItem[]> {
  return request<SimulationListItem[]>(
    `/api/v1/decisions/scenarios/${encodeURIComponent(scenarioId)}/simulations`,
  );
}
