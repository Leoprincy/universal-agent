import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Beaker,
  ChevronDown,
  ChevronRight,
  FlaskConical,
  LoaderCircle,
  Play,
  Plus,
} from "lucide-react";
import {
  createExperiment,
  evaluateExperiment,
  getExperimentHistory,
  listExperimentEvaluations,
  listExperimentOutcomes,
  listExperiments,
  listGoals,
  listStrategies,
  recordExperimentOutcome,
  transitionExperiment,
} from "../lib/api";
import type {
  Experiment,
  ExperimentEvaluation,
  ExperimentOutcome,
  ExperimentStatusHistoryEntry,
  GrowthStrategy,
  Project,
  StrategyGoal,
  SuccessCriteria,
} from "../types";

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-neutral-500/15 text-neutral-300 border-neutral-500/30",
  in_review: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  running: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  completed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  cancelled: "bg-red-500/15 text-red-300 border-red-500/30",
};

const VERDICT_STYLES: Record<string, string> = {
  succeeded: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-500/15 text-red-300 border-red-500/30",
  inconclusive: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

const NEXT_ACTIONS: Record<string, { label: string; target: string; needsReason?: boolean }[]> = {
  draft: [
    { label: "Submit for review", target: "in_review" },
    { label: "Cancel", target: "cancelled" },
  ],
  in_review: [
    { label: "Start running", target: "running" },
    { label: "Back to draft", target: "draft", needsReason: true },
    { label: "Cancel", target: "cancelled" },
  ],
  running: [
    { label: "Mark completed", target: "completed" },
    { label: "Cancel", target: "cancelled", needsReason: true },
  ],
};

function Badge({ status, styles }: { status: string; styles: Record<string, string> }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles[status] ?? "bg-neutral-500/15 text-neutral-300 border-neutral-500/30"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function fmtDate(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export function ExperimentsConsole({
  projects,
  activeProjectId,
  onSelectProject,
}: {
  projects: Project[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
}) {
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? projects[0];
  const [strategies, setStrategies] = useState<GrowthStrategy[]>([]);
  const [strategyId, setStrategyId] = useState("");
  const [goals, setGoals] = useState<StrategyGoal[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    hypothesis: "",
    goal_id: "",
    metric_name: "",
    comparator: "gte",
    threshold: "",
    min_sample_size: "",
    window_days: "",
    ends_at: "",
  });

  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<{
    outcomes: ExperimentOutcome[];
    evaluations: ExperimentEvaluation[];
    history: ExperimentStatusHistoryEntry[];
  } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [outcomeForm, setOutcomeForm] = useState({
    metric_name: "",
    value: "",
    sample_size: "",
    observed_at: "",
    notes: "",
    supersedes_id: "",
  });
  const [transitionReason, setTransitionReason] = useState("");
  const [pendingTransition, setPendingTransition] = useState<string | null>(null);

  const refreshStrategies = useCallback(async () => {
    if (!activeProject) return;
    try {
      const res = await listStrategies(activeProject.id);
      const items = res.items ?? res;
      setStrategies(items);
      setStrategyId((cur) => cur || items[0]?.id || "");
    } catch {
      setStrategies([]);
    }
  }, [activeProject]);

  const refreshExperiments = useCallback(async () => {
    if (!activeProject || !strategyId) {
      setExperiments([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await listExperiments(activeProject.id, strategyId);
      setExperiments(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load experiments");
    } finally {
      setLoading(false);
    }
  }, [activeProject, strategyId]);

  const refreshGoals = useCallback(async () => {
    if (!activeProject || !strategyId) {
      setGoals([]);
      return;
    }
    try {
      setGoals(await listGoals(activeProject.id, strategyId));
    } catch {
      setGoals([]);
    }
  }, [activeProject, strategyId]);

  useEffect(() => {
    setStrategyId("");
    setExperiments([]);
    void refreshStrategies();
  }, [activeProjectId, refreshStrategies]);

  useEffect(() => {
    void refreshExperiments();
    void refreshGoals();
  }, [refreshExperiments, refreshGoals]);

  const loadDetail = useCallback(
    async (exp: Experiment) => {
      if (!activeProject) return;
      setDetailLoading(true);
      try {
        const [outcomes, evaluations, history] = await Promise.all([
          listExperimentOutcomes(activeProject.id, strategyId, exp.id),
          listExperimentEvaluations(activeProject.id, strategyId, exp.id),
          getExperimentHistory(activeProject.id, strategyId, exp.id),
        ]);
        setDetail({ outcomes, evaluations, history });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load experiment detail");
      } finally {
        setDetailLoading(false);
      }
    },
    [activeProject, strategyId]
  );

  const toggleExpand = (exp: Experiment) => {
    if (expanded === exp.id) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(exp.id);
    setDetail(null);
    setOutcomeForm({ metric_name: "", value: "", sample_size: "", observed_at: "", notes: "", supersedes_id: "" });
    setTransitionReason("");
    setPendingTransition(null);
    void loadDetail(exp);
  };

  const handleCreate = async () => {
    if (!activeProject || !strategyId || !form.name.trim()) return;
    setError(null);
    try {
      const criteria: SuccessCriteria | undefined = form.metric_name.trim()
        ? {
            criteria: [
              {
                metric_name: form.metric_name.trim(),
                comparator: form.comparator as "gt" | "gte" | "lt" | "lte",
                threshold: Number(form.threshold),
                min_sample_size: form.min_sample_size ? Number(form.min_sample_size) : undefined,
                window_days: form.window_days ? Number(form.window_days) : undefined,
              },
            ],
          }
        : undefined;
      await createExperiment(activeProject.id, strategyId, {
        name: form.name.trim(),
        hypothesis: form.hypothesis.trim() || undefined,
        goal_id: form.goal_id || undefined,
        success_criteria: criteria,
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : undefined,
      });
      setShowCreate(false);
      setForm({ name: "", hypothesis: "", goal_id: "", metric_name: "", comparator: "gte", threshold: "", min_sample_size: "", window_days: "", ends_at: "" });
      setNotice("Experiment created.");
      void refreshExperiments();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create experiment");
    }
  };

  const handleTransition = async (exp: Experiment, target: string, needsReason?: boolean) => {
    if (!activeProject) return;
    if (needsReason && !transitionReason.trim()) {
      setPendingTransition(target);
      return;
    }
    setError(null);
    try {
      await transitionExperiment(
        activeProject.id,
        strategyId,
        exp.id,
        target,
        transitionReason.trim() || undefined
      );
      setPendingTransition(null);
      setTransitionReason("");
      setNotice(`Experiment moved to ${target.replace(/_/g, " ")}.`);
      void refreshExperiments();
      void loadDetail(exp);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transition failed");
      setPendingTransition(null);
    }
  };

  const handleOutcome = async (exp: Experiment) => {
    if (!activeProject || !outcomeForm.metric_name.trim() || !outcomeForm.value) return;
    setError(null);
    try {
      await recordExperimentOutcome(activeProject.id, strategyId, exp.id, {
        metric_name: outcomeForm.metric_name.trim(),
        value: Number(outcomeForm.value),
        sample_size: outcomeForm.sample_size ? Number(outcomeForm.sample_size) : undefined,
        observed_at: outcomeForm.observed_at
          ? new Date(outcomeForm.observed_at).toISOString()
          : new Date().toISOString(),
        notes: outcomeForm.notes.trim() || undefined,
        supersedes_id: outcomeForm.supersedes_id || undefined,
      });
      setOutcomeForm({ metric_name: "", value: "", sample_size: "", observed_at: "", notes: "", supersedes_id: "" });
      setNotice("Outcome recorded.");
      void loadDetail(exp);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to record outcome");
    }
  };

  const handleEvaluate = async (exp: Experiment) => {
    if (!activeProject) return;
    setError(null);
    try {
      await evaluateExperiment(activeProject.id, strategyId, exp.id);
      setNotice("Evaluation recorded.");
      void loadDetail(exp);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Evaluation failed");
    }
  };

  const supersededIds = useMemo(() => {
    const ids = new Set<string>();
    detail?.outcomes.forEach((o) => o.supersedes_id && ids.add(o.supersedes_id));
    return ids;
  }, [detail]);

  if (!activeProject) {
    return <section className="empty-page panel"><p>No projects yet.</p></section>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-neutral-400">Project</label>
        <select
          className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
          value={activeProject.id}
          onChange={(e) => onSelectProject(e.target.value)}
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <label className="text-xs text-neutral-400">Strategy</label>
        <select
          className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
          value={strategyId}
          onChange={(e) => setStrategyId(e.target.value)}
        >
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <button
          className="ml-auto inline-flex items-center gap-1 rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500"
          onClick={() => setShowCreate((v) => !v)}
        >
          <Plus size={14} /> New experiment
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
          {notice}
        </div>
      )}

      {showCreate && (
        <div className="panel space-y-3 p-4">
          <div className="text-sm font-semibold">New experiment</div>
          <div className="grid gap-3 md:grid-cols-2">
            <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" placeholder="Name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <select className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" value={form.goal_id} onChange={(e) => setForm({ ...form, goal_id: e.target.value })}>
              <option value="">No linked goal</option>
              {goals.map((g) => (
                <option key={g.id} value={g.id}>{g.name} ({g.metric_name})</option>
              ))}
            </select>
            <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm md:col-span-2" placeholder="Hypothesis" value={form.hypothesis} onChange={(e) => setForm({ ...form, hypothesis: e.target.value })} />
            <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" placeholder="Success metric name" value={form.metric_name} onChange={(e) => setForm({ ...form, metric_name: e.target.value })} />
            <div className="flex gap-2">
              <select className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" value={form.comparator} onChange={(e) => setForm({ ...form, comparator: e.target.value })}>
                <option value="gt">&gt;</option>
                <option value="gte">&gt;=</option>
                <option value="lt">&lt;</option>
                <option value="lte">&lt;=</option>
              </select>
              <input className="flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" placeholder="Threshold" type="number" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })} />
            </div>
            <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" placeholder="Min sample size (optional)" type="number" value={form.min_sample_size} onChange={(e) => setForm({ ...form, min_sample_size: e.target.value })} />
            <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" placeholder="Window days (optional)" type="number" value={form.window_days} onChange={(e) => setForm({ ...form, window_days: e.target.value })} />
            <label className="text-xs text-neutral-400 md:col-span-2">Observation window end (optional)
              <input type="datetime-local" className="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} />
            </label>
          </div>
          <div className="flex gap-2">
            <button className="rounded-md bg-sky-600 px-3 py-1.5 text-sm text-white hover:bg-sky-500 disabled:opacity-50" disabled={!form.name.trim()} onClick={handleCreate}>Create</button>
            <button className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm" onClick={() => setShowCreate(false)}>Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-neutral-400"><LoaderCircle className="animate-spin" size={16} /> Loading…</div>
      ) : experiments.length === 0 ? (
        <section className="empty-page panel"><p>No experiments for this strategy yet.</p></section>
      ) : (
        <div className="space-y-2">
          {experiments.map((exp) => {
            const isOpen = expanded === exp.id;
            const actions = NEXT_ACTIONS[exp.status] ?? [];
            const latestEval = detail?.evaluations[detail.evaluations.length - 1];
            return (
              <div key={exp.id} className="panel">
                <button className="flex w-full items-center gap-3 p-3 text-left" onClick={() => toggleExpand(exp)}>
                  {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  <FlaskConical size={16} className="text-sky-400" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{exp.name}</div>
                    <div className="text-xs text-neutral-400">
                      {exp.hypothesis ?? "No hypothesis"} · created {fmtDate(exp.created_at)}
                    </div>
                  </div>
                  {latestEval && isOpen && detail && (
                    <Badge status={latestEval.verdict} styles={VERDICT_STYLES} />
                  )}
                  <Badge status={exp.status} styles={STATUS_STYLES} />
                </button>

                {isOpen && (
                  <div className="border-t border-neutral-800 p-3 space-y-4">
                    {exp.hypothesis && <p className="text-sm text-neutral-300">{exp.hypothesis}</p>}
                    {exp.success_criteria?.criteria?.length ? (
                      <div className="text-xs text-neutral-400">
                        Criteria:{" "}
                        {exp.success_criteria.criteria.map((c) => (
                          <span key={c.metric_name} className="mr-2 inline-block rounded bg-neutral-800 px-1.5 py-0.5">
                            {c.metric_name} {c.comparator} {c.threshold}
                            {c.min_sample_size ? ` (n≥${c.min_sample_size})` : ""}
                            {c.window_days ? ` (${c.window_days}d)` : ""}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-amber-400">No success criteria defined — evaluation will be inconclusive.</div>
                    )}
                    <div className="text-xs text-neutral-500">
                      Started: {fmtDate(exp.started_at)} · Ends: {fmtDate(exp.ends_at)}
                    </div>

                    {/* Lifecycle actions */}
                    {actions.length > 0 && (
                      <div className="flex flex-wrap items-center gap-2">
                        {actions.map((a) => (
                          <button
                            key={a.target}
                            className="inline-flex items-center gap-1 rounded-md border border-neutral-700 px-2.5 py-1 text-xs hover:bg-neutral-800"
                            onClick={() => handleTransition(exp, a.target, a.needsReason)}
                          >
                            <Play size={12} /> {a.label}
                          </button>
                        ))}
                        {(exp.status === "running" || exp.status === "completed") && (
                          <button
                            className="inline-flex items-center gap-1 rounded-md bg-sky-700 px-2.5 py-1 text-xs text-white hover:bg-sky-600"
                            onClick={() => handleEvaluate(exp)}
                          >
                            <Beaker size={12} /> Run evaluation
                          </button>
                        )}
                      </div>
                    )}
                    {pendingTransition && (
                      <div className="flex items-center gap-2">
                        <input
                          className="flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
                          placeholder="Reason (required, min 10 chars)"
                          value={transitionReason}
                          onChange={(e) => setTransitionReason(e.target.value)}
                        />
                        <button
                          className="rounded-md bg-sky-600 px-2 py-1 text-xs text-white"
                          onClick={() => {
                            const act = actions.find((a) => a.target === pendingTransition);
                            void handleTransition(exp, pendingTransition, act?.needsReason);
                          }}
                        >
                          Confirm
                        </button>
                      </div>
                    )}

                    {detailLoading || !detail ? (
                      <div className="flex items-center gap-2 text-xs text-neutral-400"><LoaderCircle className="animate-spin" size={12} /> Loading detail…</div>
                    ) : (
                      <>
                        {/* Outcomes */}
                        <div>
                          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-400">Outcomes ({detail.outcomes.length})</div>
                          {detail.outcomes.length === 0 ? (
                            <div className="text-xs text-neutral-500">No outcomes recorded.</div>
                          ) : (
                            <div className="space-y-1">
                              {detail.outcomes.map((o) => (
                                <div key={o.id} className={`rounded border px-2 py-1.5 text-xs ${supersededIds.has(o.id) ? "border-neutral-800 opacity-50" : "border-neutral-800"}`}>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="font-medium">{o.metric_name}</span>
                                    <span className="text-sky-300">{o.value}</span>
                                    {o.sample_size != null && <span className="text-neutral-400">n={o.sample_size}</span>}
                                    <span className="text-neutral-500">{fmtDate(o.observed_at)}</span>
                                    <span className="rounded bg-neutral-800 px-1">{o.source}</span>
                                    {supersededIds.has(o.id) && <span className="text-amber-400">superseded</span>}
                                    {o.supersedes_id && <span className="text-sky-400">corrects {o.supersedes_id.slice(0, 8)}…</span>}
                                  </div>
                                  {o.notes && <div className="mt-0.5 text-neutral-400">{o.notes}</div>}
                                </div>
                              ))}
                            </div>
                          )}
                          {(exp.status === "in_review" || exp.status === "running" || exp.status === "completed") && (
                            <div className="mt-2 grid gap-2 rounded border border-neutral-800 p-2 md:grid-cols-4">
                              <input className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs" placeholder="Metric *" value={outcomeForm.metric_name} onChange={(e) => setOutcomeForm({ ...outcomeForm, metric_name: e.target.value })} />
                              <input className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs" placeholder="Value *" type="number" value={outcomeForm.value} onChange={(e) => setOutcomeForm({ ...outcomeForm, value: e.target.value })} />
                              <input className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs" placeholder="Sample size" type="number" value={outcomeForm.sample_size} onChange={(e) => setOutcomeForm({ ...outcomeForm, sample_size: e.target.value })} />
                              <input className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs" type="datetime-local" value={outcomeForm.observed_at} onChange={(e) => setOutcomeForm({ ...outcomeForm, observed_at: e.target.value })} />
                              <input className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs md:col-span-2" placeholder="Notes" value={outcomeForm.notes} onChange={(e) => setOutcomeForm({ ...outcomeForm, notes: e.target.value })} />
                              <select className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs" value={outcomeForm.supersedes_id} onChange={(e) => setOutcomeForm({ ...outcomeForm, supersedes_id: e.target.value })}>
                                <option value="">New observation</option>
                                {detail.outcomes.filter((o) => !supersededIds.has(o.id)).map((o) => (
                                  <option key={o.id} value={o.id}>Corrects: {o.metric_name}={o.value}</option>
                                ))}
                              </select>
                              <button
                                className="rounded bg-sky-700 px-2 py-1 text-xs text-white hover:bg-sky-600 disabled:opacity-50"
                                disabled={!outcomeForm.metric_name.trim() || !outcomeForm.value}
                                onClick={() => handleOutcome(exp)}
                              >
                                Record outcome
                              </button>
                            </div>
                          )}
                        </div>

                        {/* Evaluations */}
                        <div>
                          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-400">Evaluations ({detail.evaluations.length})</div>
                          {detail.evaluations.length === 0 ? (
                            <div className="text-xs text-neutral-500">No evaluations yet.</div>
                          ) : (
                            <div className="space-y-2">
                              {[...detail.evaluations].reverse().map((ev) => (
                                <div key={ev.id} className="rounded border border-neutral-800 p-2 text-xs">
                                  <div className="flex items-center gap-2">
                                    <Badge status={ev.verdict} styles={VERDICT_STYLES} />
                                    <span className="text-neutral-500">{fmtDate(ev.evaluated_at)} · by {ev.actor}</span>
                                  </div>
                                  {ev.rationale?.criteria && (
                                    <div className="mt-1 space-y-0.5">
                                      {ev.rationale.criteria.map((c, i) => (
                                        <div key={i} className="text-neutral-300">
                                          {c.metric_name}: observed {c.observed_value ?? "—"}
                                          {c.sample_size != null ? ` (n=${c.sample_size})` : ""} — {c.reason}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                  {ev.rationale?.note && (
                                    <div className="mt-1 text-neutral-500 italic">{ev.rationale.note}</div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* History */}
                        <div>
                          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-400">Status history</div>
                          <div className="space-y-1">
                            {detail.history.map((h) => (
                              <div key={h.id} className="flex items-center gap-2 text-xs text-neutral-400">
                                <span>{fmtDate(h.created_at)}</span>
                                <span>{h.previous_status ?? "—"} → {h.new_status}</span>
                                <span className="text-neutral-600">by {h.actor}</span>
                                {h.reason && <span className="text-neutral-500">({h.reason})</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
