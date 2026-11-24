export type ComponentState = "connected" | "not_configured" | "unavailable";

export interface ComponentHealth {
  status: ComponentState;
  message: string;
}

export interface HealthResponse {
  status: "healthy" | "degraded";
  application: "running";
  database: ComponentHealth;
  redis: ComponentHealth;
}

export interface SystemInfo {
  name: string;
  version: string;
  environment: string;
}

export type ProjectCategory = "mobile_app" | "web_app" | "saas" | "ecommerce" | "other";
export type ProjectStatus = "active" | "paused" | "archived";

export interface Project {
  id: string;
  name: string;
  slug: string;
  owner?: string;
  description?: string | null;
  category: ProjectCategory;
  status: ProjectStatus;
  target_audience?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  limit?: number;
  offset?: number;
}

export interface ProjectCreateInput {
  name: string;
  slug?: string;
  description?: string;
  category: ProjectCategory;
  target_audience?: string;
  metadata?: Record<string, unknown>;
}

export interface ProjectUpdateInput {
  name?: string;
  description?: string;
  category?: ProjectCategory;
  status?: ProjectStatus;
  target_audience?: string;
  metadata?: Record<string, unknown>;
}

// ─── Phase 4 Types ────────────────────────────────────────────────────────────

export type SourceType =
  | "user_interview"
  | "app_review"
  | "competitor_analysis"
  | "analytics"
  | "market_report"
  | "manual_observation";

export interface ResearchRecord {
  id: string;
  project_id: string;
  title: string;
  source_type: SourceType;
  source_url?: string | null;
  source_name?: string | null;
  author?: string | null;
  source_quote?: string | null;
  observation_summary: string;
  interpretation_notes?: string | null;
  evidence_data?: Record<string, unknown> | null;
  observed_at?: string | null;
  published_at?: string | null;
  collected_at: string;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ResearchRecordListResponse {
  items: ResearchRecord[];
  total: number;
  limit?: number;
  offset?: number;
}

export interface ResearchRecordCreateInput {
  title: string;
  source_type: SourceType;
  source_url?: string;
  source_name?: string;
  author?: string;
  source_quote?: string;
  observation_summary: string;
  interpretation_notes?: string;
  evidence_data?: Record<string, unknown>;
  observed_at?: string;
  published_at?: string;
  metadata?: Record<string, unknown>;
}

export interface ResearchRecordUpdateInput {
  title?: string;
  source_type?: SourceType;
  source_url?: string;
  source_name?: string;
  author?: string;
  source_quote?: string;
  observation_summary?: string;
  interpretation_notes?: string;
  evidence_data?: Record<string, unknown>;
  observed_at?: string;
  published_at?: string;
  metadata?: Record<string, unknown>;
}

export type OpportunityCategory =
  | "acquisition"
  | "activation"
  | "retention"
  | "referral"
  | "revenue"
  | "experimentation";

export type OpportunityStatus = "draft" | "in_review" | "approved" | "rejected" | "archived";
export type OpportunityImpact = "low" | "medium" | "high" | "critical";
export type OpportunityEffort = "low" | "medium" | "high";
export type OpportunityPriority = "p0_urgent" | "p1_high" | "p2_medium" | "p3_low";

export interface Opportunity {
  id: string;
  project_id: string;
  title: string;
  slug: string;
  problem_statement: string;
  hypothesis: string;
  proposed_mechanism: string;
  target_audience: string;
  category: OpportunityCategory;
  status: OpportunityStatus;
  estimated_impact: OpportunityImpact;
  estimated_effort: OpportunityEffort;
  confidence_score?: number | null;
  priority: OpportunityPriority;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface OpportunityListResponse {
  items: Opportunity[];
  total: number;
  limit?: number;
  offset?: number;
}

export interface OpportunityCreateInput {
  title: string;
  slug?: string;
  problem_statement: string;
  hypothesis: string;
  proposed_mechanism: string;
  target_audience: string;
  category: OpportunityCategory;
  estimated_impact: OpportunityImpact;
  estimated_effort: OpportunityEffort;
  confidence_score?: number;
  metadata?: Record<string, unknown>;
}

export interface OpportunityUpdateInput {
  title?: string;
  problem_statement?: string;
  hypothesis?: string;
  proposed_mechanism?: string;
  target_audience?: string;
  category?: OpportunityCategory;
  status?: OpportunityStatus;
  estimated_impact?: OpportunityImpact;
  estimated_effort?: OpportunityEffort;
  confidence_score?: number;
  reason?: string;
  metadata?: Record<string, unknown>;
}

export interface OpportunityTransitionInput {
  status: OpportunityStatus;
  reason?: string;
  metadata?: Record<string, unknown>;
}

export interface OpportunityStatusHistory {
  id: string;
  opportunity_id: string;
  project_id: string;
  previous_status?: string | null;
  new_status: string;
  reason?: string | null;
  actor: string;
  system_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface OpportunityStatusHistoryListResponse {
  items: OpportunityStatusHistory[];
  total: number;
}

export interface AssociatedResearch {
  research_id: string;
  opportunity_id: string;
  project_id: string;
  notes?: string | null;
  created_at: string;
  research?: ResearchRecord | null;
}

export interface AssociateResearchResponse {
  linked_count: number;
  items: AssociatedResearch[];
}

// ─── Phase 5: Strategy & Goals ──────────────────────────────────────────────

export type StrategyStatus = "draft" | "in_review" | "approved" | "active" | "completed" | "archived";

export interface GrowthStrategy {
  id: string;
  project_id: string;
  name: string;
  slug: string;
  description?: string | null;
  strategic_vision: string;
  target_audience: string;
  strategic_constraints?: string | null;
  budget_envelope?: number | null;
  currency: string;
  time_horizon: string;
  status: StrategyStatus;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface GrowthStrategyListResponse {
  items: GrowthStrategy[];
  total: number;
  limit?: number;
  offset?: number;
}

export interface GrowthStrategyCreateInput {
  name: string;
  slug?: string;
  description?: string;
  strategic_vision: string;
  target_audience: string;
  strategic_constraints?: string;
  budget_envelope?: number;
  currency?: string;
  time_horizon: string;
  metadata?: Record<string, unknown>;
}

export interface GrowthStrategyUpdateInput {
  name?: string;
  description?: string;
  strategic_vision?: string;
  target_audience?: string;
  strategic_constraints?: string;
  budget_envelope?: number;
  currency?: string;
  time_horizon?: string;
  metadata?: Record<string, unknown>;
}

export interface GrowthStrategyTransitionInput {
  status: StrategyStatus;
  reason?: string;
  metadata?: Record<string, unknown>;
}

export interface StrategyStatusHistory {
  id: string;
  strategy_id: string;
  project_id: string;
  previous_status?: StrategyStatus | null;
  new_status: StrategyStatus;
  reason?: string | null;
  actor: string;
  system_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface StrategyStatusHistoryListResponse {
  items: StrategyStatusHistory[];
  total: number;
}

export type GoalStatus = "pending" | "on_track" | "at_risk" | "behind" | "achieved" | "abandoned";

export interface StrategyGoal {
  id: string;
  project_id: string;
  strategy_id: string;
  name: string;
  description?: string | null;
  metric_name: string;
  metric_unit: string;
  baseline_value: number;
  current_value: number;
  target_value: number;
  deadline?: string | null;
  status: GoalStatus;
  progress_percentage?: number | null;
  is_increasing_metric: boolean;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface StrategyGoalCreateInput {
  name: string;
  description?: string;
  metric_name: string;
  metric_unit: string;
  baseline_value: number;
  target_value: number;
  current_value?: number;
  deadline?: string;
  status?: GoalStatus;
  metadata?: Record<string, unknown>;
}

export interface StrategyGoalUpdateInput {
  name?: string;
  description?: string;
  metric_name?: string;
  metric_unit?: string;
  baseline_value?: number;
  target_value?: number;
  current_value?: number;
  deadline?: string;
  status?: GoalStatus;
  metadata?: Record<string, unknown>;
}

export interface GoalMetricUpdate {
  id: string;
  goal_id: string;
  project_id: string;
  previous_value: number;
  new_value: number;
  notes?: string | null;
  actor: string;
  created_at: string;
}

export interface GoalMetricUpdateInput {
  new_value: number;
  notes?: string;
}

export interface GoalStatusHistory {
  id: string;
  goal_id: string;
  project_id: string;
  previous_status?: GoalStatus | null;
  new_status: GoalStatus;
  reason?: string | null;
  actor: string;
  system_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface GoalStatusHistoryListResponse {
  items: GoalStatusHistory[];
  total: number;
}

// ─── Phase 6: Integration Providers & Actions ─────────────────────────────

export type IntegrationActionStatus =
  | "pending_approval"
  | "approved"
  | "rejected"
  | "expired"
  | "executing"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface IntegrationProvider {
  id: string;
  project_id: string;
  name: string;
  adapter_type: string;
  enabled: boolean;
  sandbox_only: boolean;
  rate_limit_per_minute: number;
  config?: Record<string, unknown> | null;
  has_credential: boolean;
  created_at: string;
  updated_at: string;
}

export interface IntegrationProviderCreateInput {
  name: string;
  adapter_type?: string;
  enabled?: boolean;
  sandbox_only?: boolean;
  rate_limit_per_minute?: number;
  config?: Record<string, unknown>;
}

export interface IntegrationProviderUpdateInput {
  enabled?: boolean;
  sandbox_only?: boolean;
  rate_limit_per_minute?: number;
  config?: Record<string, unknown>;
}

export interface IntegrationAction {
  id: string;
  project_id: string;
  provider_id: string;
  action_type: string;
  payload: Record<string, unknown>;
  payload_hash: string;
  status: IntegrationActionStatus;
  idempotency_key?: string | null;
  actor: string;
  approver?: string | null;
  decision_reason?: string | null;
  pending_approval_expires_at: string;
  approval_expires_at?: string | null;
  decided_at?: string | null;
  executed_at?: string | null;
  attempt_count: number;
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IntegrationActionCreateInput {
  action_type: string;
  payload?: Record<string, unknown>;
  idempotency_key?: string;
}

export interface IntegrationActionListResponse {
  items: IntegrationAction[];
  total: number;
}

export interface IntegrationActionEvent {
  id: string;
  action_id: string;
  project_id: string;
  event_type: string;
  actor: string;
  detail?: Record<string, unknown> | null;
  seq: number;
  created_at: string;
}

export interface IntegrationCallLog {
  id: string;
  action_id: string;
  project_id: string;
  provider_id: string;
  attempt: number;
  mode: string;
  status: string;
  response_status?: number | null;
  latency_ms?: number | null;
  error?: string | null;
  created_at: string;
}

export interface AssociatedOpportunityItem {
  strategy_id: string;
  opportunity_id: string;
  project_id: string;
  strategic_rationale?: string | null;
  created_at: string;
  opportunity: Opportunity;
}

export interface StrategyOpportunityAssociateItem {
  opportunity_id: string;
  strategic_rationale?: string;
}

export interface StrategyOpportunityAssociationResponse {
  strategy_id: string;
  opportunity_id: string;
  project_id: string;
  strategic_rationale?: string | null;
  created_at: string;
}

// ─── Phase 7: Measurement & Learning ──────────────────────────────────────

export interface SuccessCriterion {
  metric_name: string;
  comparator: "gt" | "gte" | "lt" | "lte";
  threshold: number;
  min_sample_size?: number | null;
  window_days?: number | null;
}

export interface SuccessCriteria {
  criteria: SuccessCriterion[];
}

export interface Experiment {
  id: string;
  project_id: string;
  strategy_id: string;
  goal_id?: string | null;
  name: string;
  hypothesis?: string | null;
  success_criteria?: { criteria?: SuccessCriterion[] } | null;
  status: "draft" | "in_review" | "running" | "completed" | "cancelled";
  started_at?: string | null;
  ends_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExperimentListResponse {
  items: Experiment[];
  total: number;
}

export interface ExperimentOutcome {
  id: string;
  experiment_id: string;
  project_id: string;
  metric_name: string;
  value: number;
  sample_size?: number | null;
  observed_at: string;
  source: "manual" | "integration" | "import";
  source_ref?: string | null;
  notes?: string | null;
  actor: string;
  supersedes_id?: string | null;
  created_at: string;
}

export interface CriterionResult {
  metric_name: string;
  comparator: string;
  threshold: number;
  status: "pass" | "fail" | "inconclusive";
  observed_value?: number | null;
  sample_size?: number | null;
  reason: string;
}

export interface EvaluationRationale {
  criteria?: CriterionResult[];
  window?: {
    started_at?: string | null;
    ends_at?: string | null;
    evaluated_at?: string;
  };
  note?: string;
  reason?: string;
}

export interface ExperimentEvaluation {
  id: string;
  experiment_id: string;
  project_id: string;
  verdict: "succeeded" | "inconclusive" | "failed";
  rationale?: EvaluationRationale | null;
  evaluated_at: string;
  actor: string;
  created_at: string;
}

export interface ExperimentStatusHistoryEntry {
  id: string;
  experiment_id: string;
  project_id: string;
  previous_status?: string | null;
  new_status: string;
  reason?: string | null;
  actor: string;
  system_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface LearningEvidence {
  outcome_ids?: string[];
  evaluation_ids?: string[];
}

export interface LearningRecord {
  id: string;
  project_id: string;
  strategy_id?: string | null;
  experiment_id?: string | null;
  title: string;
  insight: string;
  category?: string | null;
  status: "candidate" | "validated" | "rejected";
  evidence?: { outcome_ids?: string[]; evaluation_ids?: string[] } | null;
  validated_by?: string | null;
  validated_at?: string | null;
  rejected_by?: string | null;
  rejected_at?: string | null;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LearningListResponse {
  items: LearningRecord[];
  total: number;
}

export type JobStatus = "pending" | "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Job {
  id: string;
  project_id: string;
  job_type: string;
  payload_json?: Record<string, unknown> | null;
  payload?: Record<string, unknown> | null;
  status: JobStatus;
  priority: number;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  attempt_count: number;
  max_attempts: number;
  last_error: string | null;
  idempotency_key: string | null;
  correlation_id: string | null;
  locked_by: string | null;
  locked_until: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface JobListResponse {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
}

export interface JobEvent {
  id: string;
  job_id: string;
  project_id: string;
  seq: number;
  event_type: string;
  from_status: string | null;
  to_status: string;
  message: string | null;
  actor: string;
  created_at: string;
}

export interface JobStats {
  pending: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  cancelled: number;
  with_retries: number;
}

export interface JobSchedule {
  id: string;
  project_id: string;
  name: string;
  job_type: string;
  payload: Record<string, unknown> | null;
  interval_seconds: number;
  next_run_at: string;
  last_run_at: string | null;
  enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface JobScheduleListResponse {
  items: JobSchedule[];
  total: number;
}

export interface WorkerInfo {
  worker_id: string;
  last_seen: string | null;
  age_seconds: number;
  alive: boolean;
  concurrency: number | null;
  jobs_completed: number | null;
  jobs_failed: number | null;
}

export interface OpsOverview {
  workers: WorkerInfo[];
  worker_heartbeat_store: string;
  active_workers: number;
  queue_depth: number | null;
  jobs: Record<string, number>;
  outbox: Record<string, number>;
  expired_leases: number;
  retries: Record<string, number>;
  schedules: {
    id: string; project_id: string; name: string; job_type: string;
    enabled: boolean; interval_seconds: number;
    next_run_at: string | null; last_run_at: string | null;
  }[];
}
