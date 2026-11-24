import type {
  AssociateResearchResponse,
  AssociatedOpportunityItem,
  AssociatedResearch,
  Experiment,
  ExperimentEvaluation,
  ExperimentListResponse,
  ExperimentOutcome,
  ExperimentStatusHistoryEntry,
  GoalMetricUpdate,
  GoalMetricUpdateInput,
  GoalStatus,
  GoalStatusHistoryListResponse,
  GrowthStrategy,
  GrowthStrategyCreateInput,
  GrowthStrategyListResponse,
  GrowthStrategyTransitionInput,
  GrowthStrategyUpdateInput,
  HealthResponse,
  Job,
  JobEvent,
  JobListResponse,
  JobSchedule,
  JobScheduleListResponse,
  JobStats,
  OpsOverview,
  IntegrationAction,
  IntegrationActionCreateInput,
  IntegrationActionEvent,
  IntegrationActionListResponse,
  IntegrationCallLog,
  IntegrationProvider,
  IntegrationProviderCreateInput,
  IntegrationProviderUpdateInput,
  LearningEvidence,
  LearningListResponse,
  LearningRecord,
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
  SuccessCriteria,
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

export async function getGoalStatusHistory(
  projectId: string,
  strategyIdOrSlug: string,
  goalId: string
): Promise<GoalStatusHistoryListResponse> {
  return getJson<GoalStatusHistoryListResponse>(
    `/api/v1/projects/${projectId}/strategies/${strategyIdOrSlug}/goals/${goalId}/history`
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

// ─── Phase 6: Integrations API ─────────────────────────────────────────────

async function mutateJson<T>(
  path: string,
  method: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok && response.status !== 204) {
    const errorBody = await response.json().catch(() => null);
    const msg = errorBody?.error?.message ?? `Backend returned HTTP ${response.status}`;
    throw new Error(msg);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function listIntegrationProviders(projectId: string): Promise<IntegrationProvider[]> {
  return getJson<IntegrationProvider[]>(
    `/api/v1/projects/${projectId}/integrations/providers`
  );
}

export function createIntegrationProvider(
  projectId: string,
  data: IntegrationProviderCreateInput
): Promise<IntegrationProvider> {
  return mutateJson<IntegrationProvider>(
    `/api/v1/projects/${projectId}/integrations/providers`,
    "POST",
    data
  );
}

export function updateIntegrationProvider(
  projectId: string,
  providerIdOrName: string,
  data: IntegrationProviderUpdateInput
): Promise<IntegrationProvider> {
  return mutateJson<IntegrationProvider>(
    `/api/v1/projects/${projectId}/integrations/providers/${providerIdOrName}`,
    "PATCH",
    data
  );
}

export function deleteIntegrationProvider(
  projectId: string,
  providerIdOrName: string
): Promise<void> {
  return mutateJson<void>(
    `/api/v1/projects/${projectId}/integrations/providers/${providerIdOrName}`,
    "DELETE"
  );
}

export function setIntegrationCredential(
  projectId: string,
  providerIdOrName: string,
  credential: string
): Promise<void> {
  return mutateJson<void>(
    `/api/v1/projects/${projectId}/integrations/providers/${providerIdOrName}/credential`,
    "PUT",
    { credential }
  );
}

export function listIntegrationActions(
  projectId: string,
  providerId?: string,
  status?: string
): Promise<IntegrationActionListResponse> {
  const params = new URLSearchParams();
  if (providerId) params.set("provider_id", providerId);
  if (status) params.set("status", status);
  const qs = params.toString();
  return getJson<IntegrationActionListResponse>(
    `/api/v1/projects/${projectId}/integrations/actions${qs ? `?${qs}` : ""}`
  );
}

export function createIntegrationAction(
  projectId: string,
  providerIdOrName: string,
  data: IntegrationActionCreateInput
): Promise<IntegrationAction> {
  return mutateJson<IntegrationAction>(
    `/api/v1/projects/${projectId}/integrations/providers/${providerIdOrName}/actions`,
    "POST",
    data
  );
}

export function decideIntegrationAction(
  projectId: string,
  actionId: string,
  decision: "approve" | "reject" | "cancel",
  reason?: string
): Promise<IntegrationAction> {
  return mutateJson<IntegrationAction>(
    `/api/v1/projects/${projectId}/integrations/actions/${actionId}/${decision}`,
    "POST",
    reason ? { reason } : undefined
  );
}

export function executeIntegrationAction(
  projectId: string,
  actionId: string
): Promise<IntegrationAction> {
  return mutateJson<IntegrationAction>(
    `/api/v1/projects/${projectId}/integrations/actions/${actionId}/execute`,
    "POST"
  );
}

export function getIntegrationActionEvents(
  projectId: string,
  actionId: string
): Promise<IntegrationActionEvent[]> {
  return getJson<IntegrationActionEvent[]>(
    `/api/v1/projects/${projectId}/integrations/actions/${actionId}/events`
  );
}

export function getIntegrationActionCalls(
  projectId: string,
  actionId: string
): Promise<IntegrationCallLog[]> {
  return getJson<IntegrationCallLog[]>(
    `/api/v1/projects/${projectId}/integrations/actions/${actionId}/calls`
  );
}

// ─── Phase 7: Experiments & Learnings API ─────────────────────────────────

export function listExperiments(
  projectId: string,
  strategyId: string,
  status?: string
): Promise<ExperimentListResponse> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return getJson<ExperimentListResponse>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments${q}`
  );
}

export function createExperiment(
  projectId: string,
  strategyId: string,
  data: {
    name: string;
    hypothesis?: string;
    goal_id?: string;
    success_criteria?: SuccessCriteria;
    ends_at?: string;
  }
): Promise<Experiment> {
  return mutateJson<Experiment>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments`,
    "POST",
    data
  );
}

export function getExperiment(
  projectId: string,
  strategyId: string,
  experimentId: string
): Promise<Experiment> {
  return getJson<Experiment>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments/${experimentId}`
  );
}

export function updateExperiment(
  projectId: string,
  strategyId: string,
  experimentId: string,
  data: Partial<{
    name: string;
    hypothesis: string;
    goal_id: string | null;
    success_criteria: SuccessCriteria | null;
    ends_at: string | null;
  }>
): Promise<Experiment> {
  return mutateJson<Experiment>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments/${experimentId}`,
    "PATCH",
    data
  );
}

export function transitionExperiment(
  projectId: string,
  strategyId: string,
  experimentId: string,
  status: string,
  reason?: string
): Promise<Experiment> {
  return mutateJson<Experiment>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments/${experimentId}/transition`,
    "POST",
    { status, reason }
  );
}

export function getExperimentHistory(
  projectId: string,
  strategyId: string,
  experimentId: string
): Promise<ExperimentStatusHistoryEntry[]> {
  return getJson<ExperimentStatusHistoryEntry[]>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments/${experimentId}/history`
  );
}

export function listExperimentOutcomes(
  projectId: string,
  strategyId: string,
  experimentId: string
): Promise<ExperimentOutcome[]> {
  return getJson<ExperimentOutcome[]>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments/${experimentId}/outcomes`
  );
}

export function recordExperimentOutcome(
  projectId: string,
  strategyId: string,
  experimentId: string,
  data: {
    metric_name: string;
    value: number;
    sample_size?: number;
    observed_at: string;
    source?: "manual" | "integration" | "import";
    source_ref?: string;
    notes?: string;
    supersedes_id?: string;
  }
): Promise<ExperimentOutcome> {
  return mutateJson<ExperimentOutcome>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments/${experimentId}/outcomes`,
    "POST",
    data
  );
}

export function evaluateExperiment(
  projectId: string,
  strategyId: string,
  experimentId: string
): Promise<ExperimentEvaluation> {
  return mutateJson<ExperimentEvaluation>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments/${experimentId}/evaluate`,
    "POST"
  );
}

export function listExperimentEvaluations(
  projectId: string,
  strategyId: string,
  experimentId: string
): Promise<ExperimentEvaluation[]> {
  return getJson<ExperimentEvaluation[]>(
    `/api/v1/projects/${projectId}/strategies/${strategyId}/experiments/${experimentId}/evaluations`
  );
}

export function listLearnings(
  projectId: string,
  filters?: {
    strategy_id?: string;
    experiment_id?: string;
    category?: string;
    status?: string;
  }
): Promise<LearningListResponse> {
  const params = new URLSearchParams();
  if (filters?.strategy_id) params.set("strategy_id", filters.strategy_id);
  if (filters?.experiment_id) params.set("experiment_id", filters.experiment_id);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.status) params.set("status", filters.status);
  const q = params.toString();
  return getJson<LearningListResponse>(
    `/api/v1/projects/${projectId}/learnings${q ? `?${q}` : ""}`
  );
}

export function listValidatedLearnings(
  projectId: string
): Promise<LearningListResponse> {
  return getJson<LearningListResponse>(
    `/api/v1/projects/${projectId}/learnings/validated`
  );
}

export function createLearning(
  projectId: string,
  data: {
    title: string;
    insight: string;
    category?: string;
    strategy_id?: string;
    experiment_id?: string;
    evidence?: LearningEvidence;
  }
): Promise<LearningRecord> {
  return mutateJson<LearningRecord>(
    `/api/v1/projects/${projectId}/learnings`,
    "POST",
    data
  );
}

export function updateLearning(
  projectId: string,
  learningId: string,
  data: Partial<{
    title: string;
    insight: string;
    category: string | null;
    strategy_id: string | null;
    experiment_id: string | null;
    evidence: LearningEvidence | null;
  }>
): Promise<LearningRecord> {
  return mutateJson<LearningRecord>(
    `/api/v1/projects/${projectId}/learnings/${learningId}`,
    "PATCH",
    data
  );
}

export function validateLearning(
  projectId: string,
  learningId: string
): Promise<LearningRecord> {
  return mutateJson<LearningRecord>(
    `/api/v1/projects/${projectId}/learnings/${learningId}/validate`,
    "POST"
  );
}

export function rejectLearning(
  projectId: string,
  learningId: string,
  reason: string
): Promise<LearningRecord> {
  return mutateJson<LearningRecord>(
    `/api/v1/projects/${projectId}/learnings/${learningId}/reject`,
    "POST",
    { reason }
  );
}

// ── Phase 8: Jobs & operations ─────────────────────────────────────────────

export function listJobs(
  projectId: string,
  options?: { status?: string; job_type?: string; limit?: number; offset?: number },
): Promise<JobListResponse> {
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (options?.job_type) params.set("job_type", options.job_type);
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));
  const qs = params.toString();
  return getJson<JobListResponse>(`/api/v1/projects/${projectId}/jobs${qs ? `?${qs}` : ""}`);
}

export function getJobStats(projectId: string): Promise<JobStats> {
  return getJson<JobStats>(`/api/v1/projects/${projectId}/jobs/stats`);
}

export function getJobEvents(projectId: string, jobId: string): Promise<JobEvent[]> {
  return getJson<JobEvent[]>(`/api/v1/projects/${projectId}/jobs/${jobId}/events`);
}

export function enqueueJob(projectId: string, jobId: string): Promise<Job> {
  return mutateJson<Job>(`/api/v1/projects/${projectId}/jobs/${jobId}/enqueue`, "POST");
}

export function cancelJob(projectId: string, jobId: string): Promise<Job> {
  return mutateJson<Job>(`/api/v1/projects/${projectId}/jobs/${jobId}/cancel`, "POST");
}

export function listJobSchedules(projectId: string): Promise<JobScheduleListResponse> {
  return getJson<JobScheduleListResponse>(`/api/v1/projects/${projectId}/jobs/schedules`);
}

export function createJobSchedule(
  projectId: string,
  data: { name: string; job_type: string; interval_seconds: number; payload?: Record<string, unknown>; next_run_at?: string },
): Promise<JobSchedule> {
  return mutateJson<JobSchedule>(`/api/v1/projects/${projectId}/jobs/schedules`, "POST", data);
}

export function setJobScheduleEnabled(
  projectId: string, scheduleId: string, enabled: boolean,
): Promise<JobSchedule> {
  return mutateJson<JobSchedule>(`/api/v1/projects/${projectId}/jobs/schedules/${scheduleId}/enabled`, "POST", { enabled });
}

export function getOpsOverview(): Promise<OpsOverview> {
  return getJson<OpsOverview>("/api/v1/ops/overview");
}
