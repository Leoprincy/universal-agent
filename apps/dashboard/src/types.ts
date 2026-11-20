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
