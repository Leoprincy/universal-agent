import type {
  AssociateResearchResponse,
  AssociatedResearch,
  HealthResponse,
  Opportunity,
  OpportunityCreateInput,
  OpportunityListResponse,
  OpportunityStatusHistoryListResponse,
  OpportunityTransitionInput,
  OpportunityUpdateInput,
  Project,
  ProjectCreateInput,
  ProjectListResponse,
  ProjectUpdateInput,
  ResearchRecord,
  ResearchRecordCreateInput,
  ResearchRecordListResponse,
  ResearchRecordUpdateInput,
  SystemInfo,
} from "../types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
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

export function getProject(idOrSlug: string): Promise<Project> {
  return getJson<Project>(`/api/v1/projects/${idOrSlug}`);
}

export async function updateProject(idOrSlug: string, data: ProjectUpdateInput): Promise<Project> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${idOrSlug}`, {
    method: "PATCH",
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

// ─── Research API ─────────────────────────────────────────────────────────────

export interface ListResearchOptions {
  limit?: number;
  offset?: number;
  source_type?: string;
}

export function listResearchRecords(
  projectId: string,
  options?: ListResearchOptions
): Promise<ResearchRecordListResponse> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));
  if (options?.source_type) params.set("source_type", options.source_type);
  const qs = params.toString();
  return getJson<ResearchRecordListResponse>(
    `/api/v1/projects/${projectId}/research${qs ? `?${qs}` : ""}`
  );
}

export async function createResearchRecord(
  projectId: string,
  data: ResearchRecordCreateInput
): Promise<ResearchRecord> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${projectId}/research`, {
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
  return (await response.json()) as ResearchRecord;
}

export async function updateResearchRecord(
  projectId: string,
  recordId: string,
  data: ResearchRecordUpdateInput
): Promise<ResearchRecord> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${projectId}/research/${recordId}`, {
    method: "PATCH",
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
  return (await response.json()) as ResearchRecord;
}

export async function deleteResearchRecord(projectId: string, recordId: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${projectId}/research/${recordId}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete research record: HTTP ${response.status}`);
  }
}

// ─── Opportunities API ────────────────────────────────────────────────────────

export interface ListOpportunitiesOptions {
  limit?: number;
  offset?: number;
  status?: string;
  category?: string;
  priority?: string;
}

export function listOpportunities(
  projectId: string,
  options?: ListOpportunitiesOptions
): Promise<OpportunityListResponse> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));
  if (options?.status) params.set("status", options.status);
  if (options?.category) params.set("category", options.category);
  if (options?.priority) params.set("priority", options.priority);
  const qs = params.toString();
  return getJson<OpportunityListResponse>(
    `/api/v1/projects/${projectId}/opportunities${qs ? `?${qs}` : ""}`
  );
}

export async function createOpportunity(
  projectId: string,
  data: OpportunityCreateInput
): Promise<Opportunity> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${projectId}/opportunities`, {
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
  return (await response.json()) as Opportunity;
}

export async function updateOpportunity(
  projectId: string,
  idOrSlug: string,
  data: OpportunityUpdateInput
): Promise<Opportunity> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/opportunities/${idOrSlug}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as Opportunity;
}

export async function deleteOpportunity(projectId: string, idOrSlug: string): Promise<void> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/opportunities/${idOrSlug}`,
    {
      method: "DELETE",
    }
  );
  if (!response.ok && response.status !== 204) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
}

export async function transitionOpportunity(
  projectId: string,
  idOrSlug: string,
  data: OpportunityTransitionInput
): Promise<Opportunity> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/opportunities/${idOrSlug}/transition`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as Opportunity;
}

export function getOpportunityHistory(
  projectId: string,
  idOrSlug: string
): Promise<OpportunityStatusHistoryListResponse> {
  return getJson<OpportunityStatusHistoryListResponse>(
    `/api/v1/projects/${projectId}/opportunities/${idOrSlug}/history`
  );
}

export async function associateResearch(
  projectId: string,
  idOrSlug: string,
  items: { research_id: string; notes?: string }[]
): Promise<AssociateResearchResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/opportunities/${idOrSlug}/research`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ items }),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as AssociateResearchResponse;
}

export function listAssociatedResearch(
  projectId: string,
  idOrSlug: string
): Promise<AssociatedResearch[]> {
  return getJson<AssociatedResearch[]>(
    `/api/v1/projects/${projectId}/opportunities/${idOrSlug}/research`
  );
}

export async function unlinkResearch(
  projectId: string,
  idOrSlug: string,
  researchId: string
): Promise<void> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/opportunities/${idOrSlug}/research/${researchId}`,
    {
      method: "DELETE",
    }
  );
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to unlink research: HTTP ${response.status}`);
  }
}

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}
