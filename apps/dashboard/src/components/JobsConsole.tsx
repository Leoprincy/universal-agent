import { Fragment, useCallback, useEffect, useState } from "react";
import {
  Activity,
  Ban,
  ChevronDown,
  ChevronRight,
  Clock,
  LoaderCircle,
  Play,
  RefreshCw,
  Server,
  XCircle,
} from "lucide-react";
import {
  cancelJob,
  createJobSchedule,
  enqueueJob,
  getJobEvents,
  getJobStats,
  getOpsOverview,
  listJobSchedules,
  listJobs,
  setJobScheduleEnabled,
} from "../lib/api";
import type {
  Job,
  JobEvent,
  JobSchedule,
  JobStats,
  OpsOverview,
  Project,
} from "../types";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  queued: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  running: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  completed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-500/15 text-red-300 border-red-500/30",
  cancelled: "bg-neutral-500/15 text-neutral-300 border-neutral-500/30",
};

function Badge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[status] ?? STATUS_STYLES.cancelled}`}>
      {status}
    </span>
  );
}

function fmt(iso?: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function StatCard({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-neutral-500">{label}</div>
      <div className={`text-lg font-semibold ${tone ?? "text-neutral-100"}`}>{value}</div>
    </div>
  );
}

export function JobsConsole({
  projects,
  activeProjectId,
  onSelectProject,
}: {
  projects: Project[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
}) {
  const [stats, setStats] = useState<JobStats | null>(null);
  const [ops, setOps] = useState<OpsOverview | null>(null);
  const [opsError, setOpsError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [events, setEvents] = useState<Record<string, JobEvent[]>>({});
  const [schedules, setSchedules] = useState<JobSchedule[]>([]);
  const [schedForm, setSchedForm] = useState({ name: "", job_type: "", interval_seconds: "300" });
  const limit = 20;

  const projectId = activeProjectId;

  const refresh = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [st, jb, sc] = await Promise.all([
        getJobStats(projectId),
        listJobs(projectId, {
          status: statusFilter || undefined,
          job_type: typeFilter || undefined,
          limit,
          offset,
        }),
        listJobSchedules(projectId),
      ]);
      setStats(st);
      setJobs(jb.items);
      setTotal(jb.total);
      setSchedules(sc.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
    try {
      setOps(await getOpsOverview());
      setOpsError(null);
    } catch {
      setOps(null);
      setOpsError("Operational overview unavailable");
    }
  }, [projectId, statusFilter, typeFilter, offset]);

  useEffect(() => {
    setOffset(0);
  }, [statusFilter, typeFilter, projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function toggleJob(job: Job, action: "enqueue" | "cancel") {
    if (!window.confirm(`${action === "cancel" ? "Cancel" : "Enqueue"} job ${job.id.slice(0, 8)}?`)) return;
    try {
      if (action === "enqueue") await enqueueJob(projectId, job.id);
      else await cancelJob(projectId, job.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    }
  }

  async function toggleExpand(job: Job) {
    if (expanded === job.id) {
      setExpanded(null);
      return;
    }
    setExpanded(job.id);
    if (!events[job.id]) {
      try {
        const ev = await getJobEvents(projectId, job.id);
        setEvents((prev) => ({ ...prev, [job.id]: ev }));
      } catch {
        setEvents((prev) => ({ ...prev, [job.id]: [] }));
      }
    }
  }

  async function toggleSchedule(s: JobSchedule) {
    try {
      await setJobScheduleEnabled(projectId, s.id, !s.enabled);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Schedule update failed");
    }
  }

  async function submitSchedule(e: React.FormEvent) {
    e.preventDefault();
    try {
      await createJobSchedule(projectId, {
        name: schedForm.name,
        job_type: schedForm.job_type,
        interval_seconds: parseInt(schedForm.interval_seconds, 10),
      });
      setSchedForm({ name: "", job_type: "", interval_seconds: "300" });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Schedule creation failed");
    }
  }

  const jobTypes = Array.from(new Set(jobs.map((j) => j.job_type))).sort();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-neutral-100">Jobs &amp; Background Tasks</h2>
          <p className="text-sm text-neutral-500">Persistent jobs, workers, retries and schedules</p>
        </div>
        <button className="icon-button" onClick={() => void refresh()} disabled={loading} aria-label="Refresh jobs">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {ops && (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
            <Server size={12} /> Operations
            <span className={ops.active_workers > 0 ? "text-emerald-400" : "text-amber-400"}>
              {ops.active_workers > 0 ? `${ops.active_workers} worker(s) alive` : "No active workers"}
            </span>
            {ops.queue_depth !== null && <span>queue depth {ops.queue_depth}</span>}
            {ops.expired_leases > 0 && <span className="text-red-400">{ops.expired_leases} expired lease(s)</span>}
          </div>
          <div className="flex flex-wrap gap-2 text-[11px] text-neutral-400">
            {ops.workers.slice(0, 5).map((w) => (
              <span key={w.worker_id} className={`rounded border px-1.5 py-0.5 ${w.alive ? "border-emerald-500/30 text-emerald-300" : "border-neutral-700 text-neutral-500"}`}>
                {w.worker_id.slice(0, 12)} · {w.alive ? `${Math.round(w.age_seconds)}s ago` : "stale"}
              </span>
            ))}
            {ops.workers.length === 0 && <span>No worker heartbeats{ops.worker_heartbeat_store === "unavailable" ? " (heartbeat store unavailable)" : ""}</span>}
          </div>
        </div>
      )}
      {opsError && <div className="text-xs text-amber-400">{opsError}</div>}

      {stats && (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-7">
          <StatCard label="Pending" value={stats.pending} />
          <StatCard label="Queued" value={stats.queued} />
          <StatCard label="Running" value={stats.running} tone="text-violet-300" />
          <StatCard label="Completed" value={stats.completed} tone="text-emerald-300" />
          <StatCard label="Failed" value={stats.failed} tone="text-red-300" />
          <StatCard label="Cancelled" value={stats.cancelled} />
          <StatCard label="Retries" value={stats.with_retries} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <select className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-200" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status filter">
          <option value="">All statuses</option>
          {["pending", "queued", "running", "completed", "failed", "cancelled"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-200" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} aria-label="Job type filter">
          <option value="">All types</option>
          {jobTypes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        {projects.length > 1 && (
          <select className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-200" value={projectId} onChange={(e) => onSelectProject(e.target.value)} aria-label="Project">
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
      </div>

      {error && <div className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div className="overflow-hidden rounded-lg border border-neutral-800">
        {loading && jobs.length === 0 ? (
          <div className="flex items-center gap-2 p-6 text-sm text-neutral-500"><LoaderCircle size={16} className="animate-spin" /> Loading jobs…</div>
        ) : jobs.length === 0 ? (
          <div className="p-6 text-sm text-neutral-500">No jobs{statusFilter || typeFilter ? " match the current filters" : " yet"}.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-neutral-900 text-left text-[11px] uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-3 py-2"></th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Attempts</th>
                <th className="px-3 py-2">Scheduled</th>
                <th className="px-3 py-2">Created</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <Fragment key={j.id}>
                  <tr className="border-t border-neutral-800/60 hover:bg-neutral-900/40">
                    <td className="px-3 py-2">
                      <button onClick={() => void toggleExpand(j)} aria-label="Toggle details" className="text-neutral-500">
                        {expanded === j.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      </button>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-neutral-300">{j.job_type}</td>
                    <td className="px-3 py-2"><Badge status={j.status} /></td>
                    <td className="px-3 py-2 text-neutral-400">{j.attempt_count}/{j.max_attempts}</td>
                    <td className="px-3 py-2 text-xs text-neutral-500">{fmt(j.scheduled_at)}</td>
                    <td className="px-3 py-2 text-xs text-neutral-500">{fmt(j.created_at)}</td>
                    <td className="px-3 py-2 text-right">
                      {(j.status === "pending" || j.status === "failed") && (
                        <button className="mr-1 inline-flex items-center gap-1 rounded border border-sky-500/30 px-2 py-0.5 text-[11px] text-sky-300 hover:bg-sky-500/10" onClick={() => void toggleJob(j, "enqueue")}>
                          <Play size={11} /> Enqueue
                        </button>
                      )}
                      {["pending", "queued"].includes(j.status) && (
                        <button className="inline-flex items-center gap-1 rounded border border-red-500/30 px-2 py-0.5 text-[11px] text-red-300 hover:bg-red-500/10" onClick={() => void toggleJob(j, "cancel")}>
                          <Ban size={11} /> Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                  {expanded === j.id && (
                    <tr key={`${j.id}-detail`} className="border-t border-neutral-800/40 bg-neutral-950/60">
                      <td colSpan={7} className="px-4 py-3">
                        <div className="grid gap-3 text-xs text-neutral-400 sm:grid-cols-2">
                          <div>
                            <div><span className="text-neutral-600">ID:</span> <span className="font-mono">{j.id}</span></div>
                            <div><span className="text-neutral-600">Priority:</span> {j.priority}</div>
                            <div><span className="text-neutral-600">Started:</span> {fmt(j.started_at)}</div>
                            <div><span className="text-neutral-600">Completed:</span> {fmt(j.completed_at)}</div>
                            <div><span className="text-neutral-600">Worker:</span> {j.locked_by ?? "—"}{j.locked_until ? ` (lease until ${fmt(j.locked_until)})` : ""}</div>
                            <div><span className="text-neutral-600">Correlation:</span> {j.correlation_id ?? "—"}</div>
                            <div><span className="text-neutral-600">Idempotency:</span> {j.idempotency_key ?? "—"}</div>
                          </div>
                          <div>
                            {j.last_error && (
                              <div className="mb-2 rounded border border-red-500/20 bg-red-500/5 p-2 text-red-300">
                                <XCircle size={11} className="mr-1 inline" />{j.last_error}
                              </div>
                            )}
                            <div className="text-[11px] font-medium uppercase text-neutral-600">Lifecycle</div>
                            <ul className="mt-1 space-y-0.5">
                              {(events[j.id] ?? []).map((ev) => (
                                <li key={ev.id} className="flex gap-2">
                                  <Clock size={10} className="mt-0.5 shrink-0 text-neutral-600" />
                                  <span>{fmt(ev.created_at)} · <span className="text-neutral-300">{ev.event_type}</span> {ev.from_status ? `${ev.from_status}→${ev.to_status}` : `→${ev.to_status}`} · {ev.actor}</span>
                                </li>
                              ))}
                              {(events[j.id] ?? []).length === 0 && <li className="text-neutral-600">No events loaded</li>}
                            </ul>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
        {total > limit && (
          <div className="flex items-center justify-between border-t border-neutral-800 px-3 py-2 text-xs text-neutral-500">
            <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
            <div className="flex gap-2">
              <button className="rounded border border-neutral-700 px-2 py-1 disabled:opacity-40" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Prev</button>
              <button className="rounded border border-neutral-700 px-2 py-1 disabled:opacity-40" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Next</button>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-neutral-800 p-3">
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-neutral-200">
          <Activity size={14} /> Recurring schedules
        </div>
        {schedules.length === 0 ? (
          <div className="text-xs text-neutral-500">No schedules defined for this project.</div>
        ) : (
          <ul className="space-y-1 text-xs text-neutral-400">
            {schedules.map((s) => (
              <li key={s.id} className="flex items-center justify-between rounded border border-neutral-800/60 px-2 py-1.5">
                <span>
                  <span className="font-medium text-neutral-300">{s.name}</span> · {s.job_type} · every {s.interval_seconds}s
                  <span className="ml-2 text-neutral-600">next {fmt(s.next_run_at)}</span>
                </span>
                <button
                  className={`rounded border px-2 py-0.5 text-[11px] ${s.enabled ? "border-emerald-500/30 text-emerald-300" : "border-neutral-600 text-neutral-400"}`}
                  onClick={() => void toggleSchedule(s)}
                >
                  {s.enabled ? "enabled" : "disabled"}
                </button>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={(e) => void submitSchedule(e)} className="mt-3 flex flex-wrap items-end gap-2">
          <input required placeholder="Schedule name" className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200" value={schedForm.name} onChange={(e) => setSchedForm({ ...schedForm, name: e.target.value })} />
          <input required placeholder="job.type" className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200" value={schedForm.job_type} onChange={(e) => setSchedForm({ ...schedForm, job_type: e.target.value })} />
          <input required type="number" min={1} placeholder="Interval (s)" className="w-28 rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200" value={schedForm.interval_seconds} onChange={(e) => setSchedForm({ ...schedForm, interval_seconds: e.target.value })} />
          <button type="submit" className="rounded border border-neutral-600 px-2 py-1 text-xs text-neutral-200 hover:bg-neutral-800">Add schedule</button>
        </form>
      </div>
    </div>
  );
}
