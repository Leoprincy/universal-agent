import { useCallback, useEffect, useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  LoaderCircle,
  Plus,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  createLearning,
  listExperimentEvaluations,
  listExperimentOutcomes,
  listLearnings,
  listStrategies,
  listValidatedLearnings,
  rejectLearning,
  updateLearning,
  validateLearning,
} from "../lib/api";
import type {
  ExperimentEvaluation,
  ExperimentOutcome,
  GrowthStrategy,
  LearningRecord,
  Project,
} from "../types";

const STATUS_STYLES: Record<string, string> = {
  candidate: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  validated: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  rejected: "bg-red-500/15 text-red-300 border-red-500/30",
};

function Badge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[status] ?? "bg-neutral-500/15 text-neutral-300 border-neutral-500/30"}`}>
      {status}
    </span>
  );
}

function fmtDate(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

interface EvidenceDetail {
  outcomes: ExperimentOutcome[];
  evaluations: ExperimentEvaluation[];
}

export function LearningsConsole({
  projects,
  activeProjectId,
  onSelectProject,
}: {
  projects: Project[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
}) {
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? projects[0];
  const [items, setItems] = useState<LearningRecord[]>([]);
  const [validated, setValidated] = useState<LearningRecord[]>([]);
  const [strategies, setStrategies] = useState<GrowthStrategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [filterStatus, setFilterStatus] = useState("");
  const [filterStrategy, setFilterStrategy] = useState("");
  const [filterCategory, setFilterCategory] = useState("");

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    title: "",
    insight: "",
    category: "",
    strategy_id: "",
    experiment_id: "",
  });
  const [editing, setEditing] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ title: "", insight: "", category: "" });
  const [rejectFor, setRejectFor] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const [expanded, setExpanded] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Record<string, EvidenceDetail>>({});

  const refresh = useCallback(async () => {
    if (!activeProject) return;
    setLoading(true);
    setError(null);
    try {
      const [all, valids, strats] = await Promise.all([
        listLearnings(activeProject.id, {
          status: filterStatus || undefined,
          strategy_id: filterStrategy || undefined,
          category: filterCategory || undefined,
        }),
        listValidatedLearnings(activeProject.id),
        listStrategies(activeProject.id),
      ]);
      setItems(all.items);
      setValidated(valids.items);
      setStrategies(strats.items ?? strats);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load learnings");
    } finally {
      setLoading(false);
    }
  }, [activeProject, filterStatus, filterStrategy, filterCategory]);

  useEffect(() => {
    void refresh();
  }, [activeProjectId, refresh]);

  const strategyName = (id?: string | null) =>
    strategies.find((s) => s.id === id)?.name ?? id ?? "—";

  const loadEvidence = async (rec: LearningRecord) => {
    if (!activeProject || !rec.experiment_id || !rec.strategy_id) return;
    if (evidence[rec.id]) return;
    try {
      const [outcomes, evaluations] = await Promise.all([
        listExperimentOutcomes(activeProject.id, rec.strategy_id, rec.experiment_id),
        listExperimentEvaluations(activeProject.id, rec.strategy_id, rec.experiment_id),
      ]);
      setEvidence((prev) => ({ ...prev, [rec.id]: { outcomes, evaluations } }));
    } catch {
      // Evidence detail is best-effort; IDs remain visible regardless.
    }
  };

  const toggleExpand = (rec: LearningRecord) => {
    if (expanded === rec.id) {
      setExpanded(null);
      return;
    }
    setExpanded(rec.id);
    setEditing(null);
    void loadEvidence(rec);
  };

  const handleCreate = async () => {
    if (!activeProject || !form.title.trim() || !form.insight.trim()) return;
    setError(null);
    try {
      await createLearning(activeProject.id, {
        title: form.title.trim(),
        insight: form.insight.trim(),
        category: form.category.trim() || undefined,
        strategy_id: form.strategy_id || undefined,
        experiment_id: form.experiment_id || undefined,
      });
      setShowCreate(false);
      setForm({ title: "", insight: "", category: "", strategy_id: "", experiment_id: "" });
      setNotice("Learning record created as candidate.");
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create learning");
    }
  };

  const handleUpdate = async (rec: LearningRecord) => {
    if (!activeProject) return;
    setError(null);
    try {
      await updateLearning(activeProject.id, rec.id, {
        title: editForm.title,
        insight: editForm.insight,
        category: editForm.category || null,
      });
      setEditing(null);
      setNotice("Learning updated.");
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  };

  const handleValidate = async (rec: LearningRecord) => {
    if (!activeProject) return;
    setError(null);
    try {
      await validateLearning(activeProject.id, rec.id);
      setNotice("Learning validated.");
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Validation failed");
    }
  };

  const handleReject = async (rec: LearningRecord) => {
    if (!activeProject || rejectReason.trim().length < 10) return;
    setError(null);
    try {
      await rejectLearning(activeProject.id, rec.id, rejectReason.trim());
      setRejectFor(null);
      setRejectReason("");
      setNotice("Learning rejected.");
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rejection failed");
    }
  };

  if (!activeProject) {
    return <section className="empty-page panel"><p>No projects yet.</p></section>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-neutral-400">Project</label>
        <select className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm" value={activeProject.id} onChange={(e) => onSelectProject(e.target.value)}>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="candidate">Candidate</option>
          <option value="validated">Validated</option>
          <option value="rejected">Rejected</option>
        </select>
        <select className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm" value={filterStrategy} onChange={(e) => setFilterStrategy(e.target.value)}>
          <option value="">All strategies</option>
          {strategies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm" placeholder="Category" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} />
        <button className="ml-auto inline-flex items-center gap-1 rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500" onClick={() => setShowCreate((v) => !v)}>
          <Plus size={14} /> New learning
        </button>
      </div>

      {error && <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}
      {notice && <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">{notice}</div>}

      {/* Established (validated) learning feed */}
      <div className="panel p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-emerald-400">
          <ShieldCheck size={14} /> Established learnings ({validated.length})
        </div>
        {validated.length === 0 ? (
          <div className="text-xs text-neutral-500">No validated learnings yet. Only validated records appear here.</div>
        ) : (
          <div className="space-y-1">
            {validated.map((r) => (
              <div key={r.id} className="rounded border border-emerald-900/50 bg-emerald-950/20 px-2 py-1.5 text-xs">
                <span className="font-medium text-emerald-200">{r.title}</span>
                <span className="ml-2 text-neutral-400">{r.insight.slice(0, 120)}{r.insight.length > 120 ? "…" : ""}</span>
                <span className="ml-2 text-neutral-500">validated by {r.validated_by} · {fmtDate(r.validated_at)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {showCreate && (
        <div className="panel space-y-3 p-4">
          <div className="text-sm font-semibold">New candidate learning</div>
          <div className="grid gap-3 md:grid-cols-2">
            <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" placeholder="Title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" placeholder="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            <select className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" value={form.strategy_id} onChange={(e) => setForm({ ...form, strategy_id: e.target.value })}>
              <option value="">No strategy link</option>
              {strategies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <input className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm" placeholder="Experiment ID (optional)" value={form.experiment_id} onChange={(e) => setForm({ ...form, experiment_id: e.target.value })} />
            <textarea className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm md:col-span-2" rows={3} placeholder="Insight *" value={form.insight} onChange={(e) => setForm({ ...form, insight: e.target.value })} />
          </div>
          <div className="flex gap-2">
            <button className="rounded-md bg-sky-600 px-3 py-1.5 text-sm text-white hover:bg-sky-500 disabled:opacity-50" disabled={!form.title.trim() || !form.insight.trim()} onClick={handleCreate}>Create candidate</button>
            <button className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm" onClick={() => setShowCreate(false)}>Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-neutral-400"><LoaderCircle className="animate-spin" size={16} /> Loading…</div>
      ) : items.length === 0 ? (
        <section className="empty-page panel"><p>No learning records match the current filters.</p></section>
      ) : (
        <div className="space-y-2">
          {items.map((rec) => {
            const isOpen = expanded === rec.id;
            const ev = evidence[rec.id];
            const citedOutcomes = ev ? rec.evidence?.outcome_ids?.map((id) => ev.outcomes.find((o) => o.id === id)).filter(Boolean) ?? [] : [];
            const citedEvals = ev ? rec.evidence?.evaluation_ids?.map((id) => ev.evaluations.find((e) => e.id === id)).filter(Boolean) ?? [] : [];
            return (
              <div key={rec.id} className="panel">
                <button className="flex w-full items-center gap-3 p-3 text-left" onClick={() => toggleExpand(rec)}>
                  {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  <BookOpen size={16} className="text-sky-400" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{rec.title}</span>
                      {rec.category && <span className="rounded bg-neutral-800 px-1.5 py-0.5 text-[10px] text-neutral-400">{rec.category}</span>}
                    </div>
                    <div className="text-xs text-neutral-400">{rec.insight.slice(0, 100)}{rec.insight.length > 100 ? "…" : ""}</div>
                  </div>
                  <Badge status={rec.status} />
                </button>

                {isOpen && (
                  <div className="border-t border-neutral-800 p-3 space-y-3 text-sm">
                    <p className="text-neutral-300">{rec.insight}</p>
                    <div className="grid gap-1 text-xs text-neutral-400 md:grid-cols-2">
                      <div>Strategy: {strategyName(rec.strategy_id)}</div>
                      <div>Experiment: {rec.experiment_id ? `${rec.experiment_id.slice(0, 8)}…` : "—"}</div>
                      <div>Created: {fmtDate(rec.created_at)}</div>
                      {rec.status === "validated" && <div className="text-emerald-400">Validated by {rec.validated_by} · {fmtDate(rec.validated_at)}</div>}
                      {rec.status === "rejected" && <div className="text-red-400">Rejected by {rec.rejected_by} · {fmtDate(rec.rejected_at)} — {rec.rejection_reason}</div>}
                    </div>

                    {/* Evidence */}
                    {(rec.evidence?.outcome_ids?.length || rec.evidence?.evaluation_ids?.length) ? (
                      <div>
                        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-400">Evidence</div>
                        <div className="space-y-1 text-xs">
                          {citedOutcomes.map((o) => o && (
                            <div key={o.id} className="rounded border border-neutral-800 px-2 py-1">
                              Outcome: <span className="text-sky-300">{o.metric_name}={o.value}</span> · n={o.sample_size ?? "—"} · {fmtDate(o.observed_at)} · {o.source}
                            </div>
                          ))}
                          {rec.evidence?.outcome_ids?.length && !ev && (
                            <div className="text-neutral-500">{rec.evidence.outcome_ids.length} outcome reference(s)</div>
                          )}
                          {citedEvals.map((e) => e && (
                            <div key={e.id} className="rounded border border-neutral-800 px-2 py-1">
                              Evaluation: <Badge status={e.verdict} /> · {fmtDate(e.evaluated_at)}
                            </div>
                          ))}
                          {rec.evidence?.evaluation_ids?.length && !ev && (
                            <div className="text-neutral-500">{rec.evidence.evaluation_ids.length} evaluation reference(s)</div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="text-xs text-neutral-500">No evidence references recorded.</div>
                    )}

                    {/* Actions */}
                    {rec.status === "candidate" && (
                      <div className="flex flex-wrap items-center gap-2">
                        {editing === rec.id ? (
                          <div className="w-full space-y-2">
                            <input className="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm" value={editForm.title} onChange={(e) => setEditForm({ ...editForm, title: e.target.value })} />
                            <textarea className="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm" rows={3} value={editForm.insight} onChange={(e) => setEditForm({ ...editForm, insight: e.target.value })} />
                            <input className="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm" placeholder="Category" value={editForm.category} onChange={(e) => setEditForm({ ...editForm, category: e.target.value })} />
                            <div className="flex gap-2">
                              <button className="rounded bg-sky-600 px-2 py-1 text-xs text-white" onClick={() => handleUpdate(rec)}>Save</button>
                              <button className="rounded border border-neutral-700 px-2 py-1 text-xs" onClick={() => setEditing(null)}>Cancel</button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <button className="rounded-md border border-neutral-700 px-2.5 py-1 text-xs hover:bg-neutral-800" onClick={() => { setEditing(rec.id); setEditForm({ title: rec.title, insight: rec.insight, category: rec.category ?? "" }); }}>Edit</button>
                            <button className="inline-flex items-center gap-1 rounded-md bg-emerald-700 px-2.5 py-1 text-xs text-white hover:bg-emerald-600" onClick={() => handleValidate(rec)}>
                              <CheckCircle2 size={12} /> Validate
                            </button>
                            <button className="inline-flex items-center gap-1 rounded-md bg-red-800 px-2.5 py-1 text-xs text-white hover:bg-red-700" onClick={() => setRejectFor(rec.id)}>
                              <XCircle size={12} /> Reject
                            </button>
                          </>
                        )}
                      </div>
                    )}
                    {rejectFor === rec.id && (
                      <div className="flex items-center gap-2">
                        <input className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm" placeholder="Rejection reason (min 10 chars)" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
                        <button className="rounded bg-red-700 px-2 py-1 text-xs text-white disabled:opacity-50" disabled={rejectReason.trim().length < 10} onClick={() => handleReject(rec)}>Confirm reject</button>
                      </div>
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
