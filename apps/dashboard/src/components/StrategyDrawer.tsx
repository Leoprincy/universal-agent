import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Link,
  LoaderCircle,
  Plus,
  Target,
  Trash2,
  TrendingDown,
  TrendingUp,
  Unlink,
  X,
} from "lucide-react";
import {
  associateOpportunities,
  createGoal,
  deleteGoal,
  getGoalMetricHistory,
  getStrategyHistory,
  listAssociatedOpportunities,
  listGoals,
  recordGoalProgress,
  unlinkOpportunity,
  updateGoal,
} from "../lib/api";
import type {
  AssociatedOpportunityItem,
  GoalMetricUpdate,
  GoalStatus,
  GrowthStrategy,
  Project,
  StrategyGoal,
  StrategyGoalCreateInput,
  StrategyGoalUpdateInput,
  StrategyOpportunityAssociateItem,
  StrategyStatus,
  StrategyStatusHistory,
} from "../types";
import { GoalEditorModal } from "./GoalEditorModal";
import { GoalProgressModal } from "./GoalProgressModal";
import { StrategyOpportunityLinkerModal } from "./StrategyOpportunityLinkerModal";

// ─── Helpers ────────────────────────────────────────────────────────────────

function computeProgress(goal: StrategyGoal, currentValue: number): number {
  const { baseline_value, target_value } = goal;
  if (target_value === baseline_value) return 0;
  if (target_value > baseline_value) {
    return Math.max(0, Math.min(100, ((currentValue - baseline_value) / (target_value - baseline_value)) * 100));
  }
  return Math.max(0, Math.min(100, ((baseline_value - currentValue) / (baseline_value - target_value)) * 100));
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatDateShort(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

const STRATEGY_STATUS_TONE: Record<StrategyStatus, string> = {
  draft: "neutral",
  in_review: "amber",
  approved: "emerald",
  active: "emerald",
  completed: "sky",
  archived: "neutral",
};

const STRATEGY_STATUS_LABEL: Record<StrategyStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  approved: "Approved",
  active: "Active",
  completed: "Completed",
  archived: "Archived",
};

const GOAL_STATUS_TONE: Record<GoalStatus, string> = {
  pending: "neutral",
  on_track: "emerald",
  at_risk: "amber",
  behind: "rose",
  achieved: "sky",
  abandoned: "neutral",
};

const GOAL_STATUS_LABEL: Record<GoalStatus, string> = {
  pending: "Pending",
  on_track: "On Track",
  at_risk: "At Risk",
  behind: "Behind",
  achieved: "Achieved",
  abandoned: "Abandoned",
};

// ─── Types ───────────────────────────────────────────────────────────────────

type DrawerTab = "overview" | "goals" | "opportunities" | "history";

interface StrategyDrawerProps {
  strategy: GrowthStrategy | null;
  isOpen: boolean;
  projects: Project[];
  onClose: () => void;
  onTransition: (strategy: GrowthStrategy) => void;
}

// ─── Main component ──────────────────────────────────────────────────────────

export function StrategyDrawer({
  strategy,
  isOpen,
  projects,
  onClose,
  onTransition,
}: StrategyDrawerProps) {
  const [activeTab, setActiveTab] = useState<DrawerTab>("overview");

  // Goals tab state
  const [goals, setGoals] = useState<StrategyGoal[]>([]);
  const [goalsLoading, setGoalsLoading] = useState(false);
  const [goalsError, setGoalsError] = useState<string | null>(null);
  const [goalEditorOpen, setGoalEditorOpen] = useState(false);
  const [editingGoal, setEditingGoal] = useState<StrategyGoal | null>(null);
  const [deletingGoalId, setDeletingGoalId] = useState<string | null>(null);
  const [progressGoal, setProgressGoal] = useState<StrategyGoal | null>(null);
  const [progressHistory, setProgressHistory] = useState<GoalMetricUpdate[]>([]);
  const [progressHistoryLoading, setProgressHistoryLoading] = useState(false);

  // Opportunities tab state
  const [associations, setAssociations] = useState<AssociatedOpportunityItem[]>([]);
  const [assocLoading, setAssocLoading] = useState(false);
  const [assocError, setAssocError] = useState<string | null>(null);
  const [linkerOpen, setLinkerOpen] = useState(false);
  const [unlinkingId, setUnlinkingId] = useState<string | null>(null);

  // History tab state
  const [history, setHistory] = useState<StrategyStatusHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // ── Load tab data ───────────────────────────────────────────────────────────

  const loadGoals = useCallback(async () => {
    if (!strategy) return;
    setGoalsLoading(true);
    setGoalsError(null);
    try {
      const items = await listGoals(strategy.project_id, strategy.id);
      setGoals(items);
    } catch (err) {
      setGoalsError(err instanceof Error ? err.message : "Failed to load goals.");
    } finally {
      setGoalsLoading(false);
    }
  }, [strategy]);

  const loadAssociations = useCallback(async () => {
    if (!strategy) return;
    setAssocLoading(true);
    setAssocError(null);
    try {
      const items = await listAssociatedOpportunities(strategy.project_id, strategy.id);
      setAssociations(items);
    } catch (err) {
      setAssocError(err instanceof Error ? err.message : "Failed to load linked opportunities.");
    } finally {
      setAssocLoading(false);
    }
  }, [strategy]);

  const loadHistory = useCallback(async () => {
    if (!strategy) return;
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const res = await getStrategyHistory(strategy.project_id, strategy.id);
      setHistory(res.items);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Failed to load history.");
    } finally {
      setHistoryLoading(false);
    }
  }, [strategy]);

  const strategyId = strategy?.id;
  useEffect(() => {
    if (isOpen && strategy) {
      setActiveTab("overview");
      setGoals([]);
      setAssociations([]);
      setHistory([]);
    }
  // Reset state when the drawer opens or the selected strategy changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, strategyId]);

  useEffect(() => {
    if (!isOpen || !strategy) return;
    if (activeTab === "goals") void loadGoals();
    if (activeTab === "opportunities") void loadAssociations();
    if (activeTab === "history") void loadHistory();
  }, [activeTab, isOpen, strategy, loadGoals, loadAssociations, loadHistory]);

  // ── Goal actions ────────────────────────────────────────────────────────────

  const handleGoalSubmit = async (data: StrategyGoalCreateInput | StrategyGoalUpdateInput) => {
    if (!strategy) return;
    if (editingGoal) {
      const updated = await updateGoal(strategy.project_id, strategy.id, editingGoal.id, data as StrategyGoalUpdateInput);
      setGoals((prev) => prev.map((g) => (g.id === updated.id ? updated : g)));
    } else {
      const created = await createGoal(strategy.project_id, strategy.id, data as StrategyGoalCreateInput);
      setGoals((prev) => [created, ...prev]);
    }
    setEditingGoal(null);
    setGoalEditorOpen(false);
  };

  const handleDeleteGoal = async (goalId: string) => {
    if (!strategy) return;
    setDeletingGoalId(goalId);
    try {
      await deleteGoal(strategy.project_id, strategy.id, goalId);
      setGoals((prev) => prev.filter((g) => g.id !== goalId));
    } finally {
      setDeletingGoalId(null);
    }
  };

  const openProgressModal = async (goal: StrategyGoal) => {
    if (!strategy) return;
    setProgressGoal(goal);
    setProgressHistoryLoading(true);
    try {
      const items = await getGoalMetricHistory(strategy.project_id, strategy.id, goal.id);
      setProgressHistory(items);
    } catch {
      setProgressHistory([]);
    } finally {
      setProgressHistoryLoading(false);
    }
  };

  const handleProgressSubmit = async (newValue: number, notes?: string) => {
    if (!strategy || !progressGoal) return;
    const update = await recordGoalProgress(strategy.project_id, strategy.id, progressGoal.id, { new_value: newValue, notes });
    setProgressHistory((prev) => [...prev, update]);
    // Refresh goal list to pick up status changes
    void loadGoals();
  };

  // ── Opportunity actions ─────────────────────────────────────────────────────

  const handleAssociate = async (items: StrategyOpportunityAssociateItem[]) => {
    if (!strategy) return;
    await associateOpportunities(strategy.project_id, strategy.id, items);
    await loadAssociations();
  };

  const handleUnlink = async (opportunityId: string) => {
    if (!strategy) return;
    setUnlinkingId(opportunityId);
    try {
      await unlinkOpportunity(strategy.project_id, strategy.id, opportunityId);
      setAssociations((prev) => prev.filter((a) => a.opportunity_id !== opportunityId));
    } finally {
      setUnlinkingId(null);
    }
  };

  if (!isOpen || !strategy) return null;

  const linkedIds = new Set(associations.map((a) => a.opportunity_id));

  return (
    <>
      {/* Backdrop */}
      <div
        className="drawer-backdrop"
        onClick={onClose}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 40 }}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        className="drawer-panel"
        role="dialog"
        aria-modal="true"
        aria-label={`Strategy: ${strategy.name}`}
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(640px, 100vw)",
          background: "var(--color-surface, #0f1117)",
          borderLeft: "1px solid rgba(255,255,255,0.08)",
          zIndex: 50,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Drawer header */}
        <div style={{ padding: "20px 24px 0", borderBottom: "1px solid rgba(255,255,255,0.06)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="eyebrow" style={{ marginBottom: 4 }}>
                <span className="eyebrow-line" /> STRATEGY
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, lineHeight: 1.3 }}>{strategy.name}</h2>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                <span className={`status-badge ${STRATEGY_STATUS_TONE[strategy.status]}`}>
                  <span className="status-dot" />{STRATEGY_STATUS_LABEL[strategy.status]}
                </span>
                {strategy.time_horizon && (
                  <span style={{ fontSize: 11, color: "var(--color-muted, #6b7280)", display: "flex", alignItems: "center", gap: 4 }}>
                    <Clock size={11} /> {strategy.time_horizon.replace(/_/g, " ")}
                  </span>
                )}
                {strategy.budget_envelope != null && (
                  <span style={{ fontSize: 11, color: "var(--color-muted, #6b7280)" }}>
                    Budget: {strategy.budget_envelope.toLocaleString()}{strategy.currency ? ` ${strategy.currency}` : ""}
                  </span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
              <button
                className="btn btn-ghost"
                style={{ fontSize: 12, padding: "4px 10px" }}
                onClick={() => onTransition(strategy)}
                title="Manage lifecycle transition"
              >
                <ChevronRight size={13} /> Transition
              </button>
              <button className="icon-button" onClick={onClose} aria-label="Close drawer">
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display: "flex", gap: 0, borderBottom: "none" }}>
            {(["overview", "goals", "opportunities", "history"] as DrawerTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  background: "none",
                  border: "none",
                  borderBottom: `2px solid ${activeTab === tab ? "var(--color-primary, #6366f1)" : "transparent"}`,
                  color: activeTab === tab ? "#fff" : "var(--color-muted, #6b7280)",
                  fontWeight: activeTab === tab ? 600 : 400,
                  fontSize: 13,
                  padding: "8px 14px 10px",
                  cursor: "pointer",
                  transition: "color 0.15s, border-color 0.15s",
                  textTransform: "capitalize",
                }}
                aria-selected={activeTab === tab}
              >
                {tab === "goals" ? "Goals & KRs" : tab === "opportunities" ? "Linked Opps" : tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {/* ── Overview ── */}
          {activeTab === "overview" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {strategy.strategic_vision && (
                <OverviewRow label="Strategic vision" value={strategy.strategic_vision} multiline />
              )}
              {strategy.target_audience && (
                <OverviewRow label="Target audience" value={strategy.target_audience} />
              )}
              {strategy.strategic_constraints && (
                <OverviewRow label="Constraints" value={strategy.strategic_constraints} multiline />
              )}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {strategy.time_horizon && (
                  <OverviewRow label="Time horizon" value={strategy.time_horizon.replace(/_/g, " ")} />
                )}
                {strategy.budget_envelope != null && (
                  <OverviewRow
                    label="Budget envelope"
                    value={`${strategy.budget_envelope.toLocaleString()}${strategy.currency ? ` ${strategy.currency}` : ""}`}
                  />
                )}
                <OverviewRow label="Created" value={formatDateShort(strategy.created_at)} />
                <OverviewRow label="Updated" value={formatDateShort(strategy.updated_at)} />
              </div>
            </div>
          )}

          {/* ── Goals ── */}
          {activeTab === "goals" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Measurable goals</span>
                <button
                  className="btn btn-primary"
                  style={{ fontSize: 12, padding: "4px 12px" }}
                  onClick={() => { setEditingGoal(null); setGoalEditorOpen(true); }}
                >
                  <Plus size={13} /> Add goal
                </button>
              </div>

              {goalsLoading && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-muted, #6b7280)", fontSize: 13 }}>
                  <LoaderCircle size={13} className="spin" /> Loading goals…
                </div>
              )}
              {goalsError && (
                <div className="modal-error" role="alert"><AlertCircle size={13} /><span>{goalsError}</span></div>
              )}
              {!goalsLoading && !goalsError && goals.length === 0 && (
                <div style={{ color: "var(--color-muted, #6b7280)", fontSize: 13 }}>No goals added yet. Add a measurable goal to track progress.</div>
              )}

              {goals.map((goal) => {
                const isIncreasing = goal.target_value > goal.baseline_value;
                const pct = computeProgress(goal, goal.current_value ?? goal.baseline_value);
                const barColor = pct >= 80 ? "var(--color-emerald, #10b981)" : pct >= 40 ? "var(--color-amber, #f59e0b)" : "var(--color-rose, #f43f5e)";
                return (
                  <div key={goal.id} className="panel" style={{ padding: "14px 16px", marginBottom: 10, borderRadius: 8 }}>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{goal.name}</span>
                          <span className={`status-badge ${GOAL_STATUS_TONE[goal.status]}`} style={{ fontSize: 10 }}>
                            <span className="status-dot" />{GOAL_STATUS_LABEL[goal.status]}
                          </span>
                          {isIncreasing
                            ? <TrendingUp size={12} style={{ color: "var(--color-emerald, #10b981)" }} />
                            : <TrendingDown size={12} style={{ color: "var(--color-amber, #f59e0b)" }} />
                          }
                        </div>
                        <div style={{ fontSize: 11, color: "var(--color-muted, #6b7280)", marginBottom: 8 }}>
                          {goal.metric_name}: {goal.baseline_value} → {goal.target_value}
                          {goal.metric_unit ? ` ${goal.metric_unit}` : ""}
                          {goal.deadline && <span style={{ marginLeft: 8 }}>· Due {formatDateShort(goal.deadline)}</span>}
                        </div>
                        {/* Progress bar */}
                        <div>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--color-muted, #6b7280)", marginBottom: 3 }}>
                            <span>Progress</span>
                            <span>{pct.toFixed(1)}%</span>
                          </div>
                          <div style={{ height: 4, background: "rgba(255,255,255,0.08)", borderRadius: 3, overflow: "hidden" }}>
                            <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 3 }} />
                          </div>
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 4, flexShrink: 0, marginLeft: 8 }}>
                        <button
                          className="btn btn-ghost"
                          style={{ fontSize: 11, padding: "3px 8px" }}
                          onClick={() => void openProgressModal(goal)}
                          title="Record progress check-in"
                        >
                          <Target size={11} /> Check-in
                        </button>
                        <button
                          className="icon-button"
                          onClick={() => { setEditingGoal(goal); setGoalEditorOpen(true); }}
                          title="Edit goal"
                        >
                          <CheckCircle2 size={13} />
                        </button>
                        <button
                          className="icon-button"
                          onClick={() => void handleDeleteGoal(goal.id)}
                          disabled={deletingGoalId === goal.id}
                          title="Delete goal"
                          style={{ color: "var(--color-rose, #f43f5e)" }}
                        >
                          {deletingGoalId === goal.id ? <LoaderCircle size={13} className="spin" /> : <Trash2 size={13} />}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Linked Opportunities ── */}
          {activeTab === "opportunities" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>Linked opportunities</span>
                <button
                  className="btn btn-primary"
                  style={{ fontSize: 12, padding: "4px 12px" }}
                  onClick={() => setLinkerOpen(true)}
                >
                  <Link size={13} /> Link opportunity
                </button>
              </div>

              {assocLoading && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-muted, #6b7280)", fontSize: 13 }}>
                  <LoaderCircle size={13} className="spin" /> Loading…
                </div>
              )}
              {assocError && (
                <div className="modal-error" role="alert"><AlertCircle size={13} /><span>{assocError}</span></div>
              )}
              {!assocLoading && !assocError && associations.length === 0 && (
                <div style={{ color: "var(--color-muted, #6b7280)", fontSize: 13 }}>No opportunities linked yet.</div>
              )}

              {associations.map((assoc) => {
                const opp = assoc.opportunity;
                return (
                  <div key={assoc.opportunity_id} className="panel" style={{ padding: "12px 14px", marginBottom: 8, borderRadius: 8 }}>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 3 }}>{opp.title}</div>
                        {assoc.strategic_rationale && (
                          <div style={{ fontSize: 12, color: "var(--color-muted, #6b7280)", marginBottom: 3 }}>
                            Rationale: {assoc.strategic_rationale}
                          </div>
                        )}
                        <div style={{ fontSize: 11, color: "var(--color-muted, #6b7280)" }}>
                          Status: {opp.status.replace(/_/g, " ")} · Linked {formatDateShort(assoc.created_at)}
                        </div>
                      </div>
                      <button
                        className="icon-button"
                        onClick={() => void handleUnlink(assoc.opportunity_id)}
                        disabled={unlinkingId === assoc.opportunity_id}
                        title="Unlink opportunity"
                        style={{ flexShrink: 0 }}
                      >
                        {unlinkingId === assoc.opportunity_id ? <LoaderCircle size={13} className="spin" /> : <Unlink size={13} />}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── Audit History ── */}
          {activeTab === "history" && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 14 }}>Status transition history</div>
              {historyLoading && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-muted, #6b7280)", fontSize: 13 }}>
                  <LoaderCircle size={13} className="spin" /> Loading history…
                </div>
              )}
              {historyError && (
                <div className="modal-error" role="alert"><AlertCircle size={13} /><span>{historyError}</span></div>
              )}
              {!historyLoading && !historyError && history.length === 0 && (
                <div style={{ color: "var(--color-muted, #6b7280)", fontSize: 13 }}>No transitions recorded yet.</div>
              )}
              {[...history].reverse().map((entry, i) => (
                <div key={i} style={{ display: "flex", gap: 12, padding: "10px 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <div style={{ flexShrink: 0, marginTop: 2 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-primary, #6366f1)", margin: "4px auto" }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 500 }}>
                      {entry.previous_status ? (
                        <>
                          <span className={`status-badge ${STRATEGY_STATUS_TONE[entry.previous_status]}`} style={{ fontSize: 10 }}>
                            {STRATEGY_STATUS_LABEL[entry.previous_status]}
                          </span>
                          <ChevronRight size={12} style={{ color: "var(--color-muted, #6b7280)" }} />
                        </>
                      ) : null}
                      <span className={`status-badge ${STRATEGY_STATUS_TONE[entry.new_status]}`} style={{ fontSize: 10 }}>
                        {STRATEGY_STATUS_LABEL[entry.new_status]}
                      </span>
                    </div>
                    {entry.reason && (
                      <div style={{ fontSize: 12, color: "var(--color-muted, #6b7280)", marginTop: 3 }}>{entry.reason}</div>
                    )}
                    <div style={{ fontSize: 11, color: "var(--color-muted, #6b7280)", marginTop: 2 }}>
                      {formatDate(entry.created_at)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Sub-modals */}
      <GoalEditorModal
        isOpen={goalEditorOpen}
        goal={editingGoal}
        strategyId={strategy.id}
        onClose={() => { setGoalEditorOpen(false); setEditingGoal(null); }}
        onSubmit={handleGoalSubmit}
      />

      <GoalProgressModal
        isOpen={!!progressGoal}
        goal={progressGoal}
        history={progressHistory}
        historyLoading={progressHistoryLoading}
        onClose={() => setProgressGoal(null)}
        onSubmit={handleProgressSubmit}
      />

      <StrategyOpportunityLinkerModal
        isOpen={linkerOpen}
        projectId={strategy.project_id}
        strategyId={strategy.id}
        strategyStatus={strategy.status}
        linkedOpportunityIds={linkedIds}
        projects={projects}
        onClose={() => setLinkerOpen(false)}
        onSubmit={handleAssociate}
      />
    </>
  );
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function OverviewRow({ label, value, multiline }: { label: string; value: string; multiline?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", color: "var(--color-muted, #6b7280)", marginBottom: 4 }}>
        {label.toUpperCase()}
      </div>
      {multiline ? (
        <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{value}</div>
      ) : (
        <div style={{ fontSize: 13 }}>{value}</div>
      )}
    </div>
  );
}
