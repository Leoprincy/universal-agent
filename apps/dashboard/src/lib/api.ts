import type { HealthResponse, SystemInfo } from "../types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Backend returned HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/v1/health");
}

export function getSystemInfo(): Promise<SystemInfo> {
  return getJson<SystemInfo>("/api/v1/system/info");
}

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}
