import type {
  AssociateResearchResponse,
  AssociatedOpportunityItem,
  AssociatedResearch,
  GoalMetricUpdate,
  GoalMetricUpdateInput,
  GoalStatus,
  GrowthStrategy,
  GrowthStrategyCreateInput,
  GrowthStrategyListResponse,
  GrowthStrategyTransitionInput,
  GrowthStrategyUpdateInput,
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
  StrategyGoal,
  StrategyGoalCreateInput,
  StrategyGoalUpdateInput,
  StrategyOpportunityAssociateItem,
  StrategyOpportunityAssociationResponse,
  StrategyStatus,
  StrategyStatusHistoryListResponse,
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

// ─── Phase 5: Strategy & Goals ──────────────────────────────────────────────

export async function listStrategies(
  projectId: string,
  params?: { status?: StrategyStatus; time_horizon?: string; limit?: number; offset?: number }
): Promise<GrowthStrategyListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.time_horizon) query.set("time_horizon", params.time_horizon);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString() ? `?${query.toString()}` : "";
  return getJson<GrowthStrategyListResponse>(`/api/v1/projects/${projectId}/strategies${qs}`);
}

export async function getStrategy(projectId: string, idOrSlug: string): Promise<GrowthStrategy> {
  return getJson<GrowthStrategy>(`/api/v1/projects/${projectId}/strategies/${idOrSlug}`);
}

export async function createStrategy(
  projectId: string,
  data: GrowthStrategyCreateInput
): Promise<GrowthStrategy> {
  const response = await fetch(`${apiBaseUrl}/api/v1/projects/${projectId}/strategies`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as GrowthStrategy;
}

export async function updateStrategy(
  projectId: string,
  idOrSlug: string,
  data: GrowthStrategyUpdateInput
): Promise<GrowthStrategy> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${idOrSlug}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as GrowthStrategy;
}

export async function deleteStrategy(projectId: string, idOrSlug: string): Promise<void> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${idOrSlug}`,
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

export async function transitionStrategy(
  projectId: string,
  idOrSlug: string,
  data: GrowthStrategyTransitionInput
): Promise<GrowthStrategy> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${idOrSlug}/transition`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as GrowthStrategy;
}

export async function getStrategyHistory(
  projectId: string,
  idOrSlug: string
): Promise<StrategyStatusHistoryListResponse> {
  return getJson<StrategyStatusHistoryListResponse>(
    `/api/v1/projects/${projectId}/strategies/${idOrSlug}/history`
  );
}

// ─── Strategic Goals API ────────────────────────────────────────────────────

export async function listGoals(
  projectId: string,
  strategyIdOrSlug: string,
  status?: GoalStatus
): Promise<StrategyGoal[]> {
  const qs = status ? `?status=${status}` : "";
  return getJson<StrategyGoal[]>(
    `/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/goals${qs}`
  );
}

export async function getGoal(
  projectId: string,
  strategyIdOrSlug: string,
  goalId: string
): Promise<StrategyGoal> {
  return getJson<StrategyGoal>(
    `/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/goals/${goalId}`
  );
}

export async function createGoal(
  projectId: string,
  strategyIdOrSlug: string,
  data: StrategyGoalCreateInput
): Promise<StrategyGoal> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/goals`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as StrategyGoal;
}

export async function updateGoal(
  projectId: string,
  strategyIdOrSlug: string,
  goalId: string,
  data: StrategyGoalUpdateInput
): Promise<StrategyGoal> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/goals/${goalId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as StrategyGoal;
}

export async function deleteGoal(
  projectId: string,
  strategyIdOrSlug: string,
  goalId: string
): Promise<void> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/goals/${goalId}`,
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

export async function recordGoalProgress(
  projectId: string,
  strategyIdOrSlug: string,
  goalId: string,
  data: GoalMetricUpdateInput
): Promise<GoalMetricUpdate> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/goals/${goalId}/progress`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(data),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as GoalMetricUpdate;
}

export async function getGoalMetricHistory(
  projectId: string,
  strategyIdOrSlug: string,
  goalId: string
): Promise<GoalMetricUpdate[]> {
  return getJson<GoalMetricUpdate[]>(
    `/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/goals/${goalId}/progress`
  );
}

// ─── Opportunity Associations API ───────────────────────────────────────────

export async function listAssociatedOpportunities(
  projectId: string,
  strategyIdOrSlug: string
): Promise<AssociatedOpportunityItem[]> {
  return getJson<AssociatedOpportunityItem[]>(
    `/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/opportunities`
  );
}

export async function associateOpportunities(
  projectId: string,
  strategyIdOrSlug: string,
  items: StrategyOpportunityAssociateItem[]
): Promise<StrategyOpportunityAssociationResponse[]> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/opportunities`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ items }),
    }
  );
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  return (await response.json()) as StrategyOpportunityAssociationResponse[];
}

export async function unlinkOpportunity(
  projectId: string,
  strategyIdOrSlug: string,
  opportunityId: string
): Promise<void> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/opportunities/${opportunityId}`,
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

export function getApiBaseUrl(): string {
  return apiBaseUrl;
}
