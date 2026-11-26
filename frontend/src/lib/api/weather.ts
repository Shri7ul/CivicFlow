import type { ApiRequester } from "@/lib/api/incidents";
import type { WeatherAssessment, WeatherConfig } from "@/types/weather";

const JSON_HEADERS = { "Content-Type": "application/json" };

export function getWeatherAssessment(
  request: ApiRequester,
  incidentId: string,
): Promise<WeatherAssessment> {
  return request(`/api/v1/weather/incidents/${incidentId}/assessment`);
}

export function refreshWeatherAssessment(
  request: ApiRequester,
  incidentId: string,
  reason?: string,
): Promise<WeatherAssessment> {
  return request(
    `/api/v1/weather/incidents/${incidentId}/assessment/refresh`,
    {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(reason ? { reason } : {}),
    },
  );
}

export function getWeatherConfig(request: ApiRequester): Promise<WeatherConfig> {
  return request("/api/v1/weather/config");
}
