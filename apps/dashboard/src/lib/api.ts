import type {
  HealthResponse,
  Project,
  ProjectCreateInput,
  ProjectListResponse,
  SystemInfo,
} from "../types";

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

export interface ListProjectsOptions {
  limit?: number;
  offset?: number;
  status?: string;
  category?: string;
}

export function listProjects(options?: ListProjectsOptions): Promise<ProjectListResponse> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));
  if (options?.status) params.set("status", options.status);
  if (options?.category) params.set("category", options.category);
  const qs = params.toString();
  return getJson<ProjectListResponse>(`/api/v1/projects${qs ? `?${qs}` : ""}`);
}

export async function createProject(data: ProjectCreateInput): Promise<Project> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as Project;
}

export async function deleteProject(id: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${id}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete project: HTTP ${response.status}`);
  }
}

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}
