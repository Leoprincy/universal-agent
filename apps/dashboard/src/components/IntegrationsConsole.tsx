import { Fragment, useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  LoaderCircle,
  Play,
  Plug,
  Plus,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  createIntegrationAction,
  createIntegrationProvider,
  decideIntegrationAction,
  executeIntegrationAction,
  getIntegrationActionCalls,
  getIntegrationActionEvents,
  listIntegrationActions,
  listIntegrationProviders,
  setIntegrationCredential,
  updateIntegrationProvider,
} from "../lib/api";
import type {
  IntegrationAction,
  IntegrationActionEvent,
  IntegrationCallLog,
  IntegrationProvider,
  Project,
} from "../types";

const STATUS_STYLES: Record<string, string> = {
  pending_approval: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  approved: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  executing: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  succeeded: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-500/15 text-red-300 border-red-500/30",
  rejected: "bg-red-500/15 text-red-300 border-red-500/30",
  cancelled: "bg-neutral-500/15 text-neutral-400 border-neutral-500/30",
  expired: "bg-neutral-500/15 text-neutral-400 border-neutral-500/30",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[status] ?? "bg-neutral-500/15 text-neutral-300 border-neutral-500/30"}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function IntegrationsConsole({
  projects,
  activeProjectId,
  onSelectProject,
}: {
  projects: Project[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
}) {
  const [providers, setProviders] = useState<IntegrationProvider[]>([]);
  const [actions, setActions] = useState<IntegrationAction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showProviderForm, setShowProviderForm] = useState(false);
  const [newProviderName, setNewProviderName] = useState("");
  const [newProviderRate, setNewProviderRate] = useState("60");
  const [showActionForm, setShowActionForm] = useState<string | null>(null);
  const [actionType, setActionType] = useState("sandbox_action");
  const [actionPayload, setActionPayload] = useState("{}");
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [actionDetail, setActionDetail] = useState<{
    events: IntegrationActionEvent[];
    calls: IntegrationCallLog[];
  } | null>(null);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? projects[0];

  const refresh = useCallback(async () => {
    if (!activeProject) return;
    setLoading(true);
    setError(null);
    try {
      const [provs, acts] = await Promise.all([
        listIntegrationProviders(activeProject.id),
        listIntegrationActions(activeProject.id),
      ]);
      setProviders(provs);
      setActions(acts.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrations");
    } finally {
      setLoading(false);
    }
  }, [activeProject]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleCreateProvider = async () => {
    if (!activeProject || !newProviderName.trim()) return;
    try {
      await createIntegrationProvider(activeProject.id, {
        name: newProviderName.trim(),
        adapter_type: "sandbox",
        sandbox_only: true,
        rate_limit_per_minute: Math.max(1, parseInt(newProviderRate, 10) || 60),
      });
      setNewProviderName("");
      setShowProviderForm(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create provider");
    }
  };

  const handleToggleProvider = async (p: IntegrationProvider) => {
    if (!activeProject) return;
    try {
      await updateIntegrationProvider(activeProject.id, p.id, { enabled: !p.enabled });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update provider");
    }
  };

  const handleSetCredential = async (p: IntegrationProvider) => {
    if (!activeProject) return;
    const value = window.prompt(`Credential JSON for "${p.name}" (stored encrypted, never shown again):`);
    if (!value) return;
    try {
      await setIntegrationCredential(activeProject.id, p.id, value);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to store credential");
    }
  };

  const handleCreateAction = async (providerId: string) => {
    if (!activeProject) return;
    let payload: Record<string, unknown> = {};
    try {
      payload = JSON.parse(actionPayload || "{}");
    } catch {
      setError("Action payload must be valid JSON");
      return;
    }
    try {
      await createIntegrationAction(activeProject.id, providerId, {
        action_type: actionType.trim() || "sandbox_action",
        payload,
      });
      setShowActionForm(null);
      setActionPayload("{}");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create action");
    }
  };

  const handleDecide = async (action: IntegrationAction, decision: "approve" | "reject" | "cancel") => {
    if (!activeProject) return;
    const reason = decision === "approve" ? undefined : window.prompt(`Reason for ${decision}:`) ?? undefined;
    try {
      await decideIntegrationAction(activeProject.id, action.id, decision, reason);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${decision} action`);
    }
  };

  const handleExecute = async (action: IntegrationAction) => {
    if (!activeProject) return;
    try {
      await executeIntegrationAction(activeProject.id, action.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute action");
    }
  };

  const toggleDetail = async (action: IntegrationAction) => {
    if (!activeProject) return;
    if (expandedAction === action.id) {
      setExpandedAction(null);
      setActionDetail(null);
      return;
    }
    setExpandedAction(action.id);
    setActionDetail(null);
    try {
      const [events, calls] = await Promise.all([
        getIntegrationActionEvents(activeProject.id, action.id),
        getIntegrationActionCalls(activeProject.id, action.id),
      ]);
      setActionDetail({ events, calls });
    } catch {
      setActionDetail({ events: [], calls: [] });
    }
  };

  if (!activeProject) {
    return <div className="p-8 text-center text-neutral-400">Create a project first.</div>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> EXECUTION ADAPTERS</div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            Integrations<span className="heading-period">.</span>
          </h1>
          <p className="page-subtitle">
            Provider adapters, credential vault, approval-gated actions, and immutable audit trails.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white"
            value={activeProject.id}
            onChange={(e) => onSelectProject(e.target.value)}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id} className="bg-neutral-900 text-white">
                {p.name}
              </option>
            ))}
          </select>
          <button className="button button-primary" onClick={() => setShowProviderForm((v) => !v)}>
            <Plus size={14} /> Provider
          </button>
        </div>
      </div>

      {error && (
        <div className="workspace-alert" role="alert">
          <span>{error}</span>
          <button onClick={() => setError(null)} aria-label="Dismiss"><XCircle size={14} /></button>
        </div>
      )}

      {showProviderForm && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-4 flex flex-wrap items-end gap-3">
          <label className="text-xs text-neutral-400 flex flex-col gap-1">
            Name
            <input
              className="bg-neutral-900 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white"
              value={newProviderName}
              onChange={(e) => setNewProviderName(e.target.value)}
              placeholder="e.g. Sandbox Channel"
            />
          </label>
          <label className="text-xs text-neutral-400 flex flex-col gap-1">
            Rate limit / min
            <input
              className="bg-neutral-900 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white w-24"
              value={newProviderRate}
              onChange={(e) => setNewProviderRate(e.target.value)}
            />
          </label>
          <button className="button button-primary" onClick={handleCreateProvider} disabled={!newProviderName.trim()}>
            Create
          </button>
          <span className="text-[11px] text-neutral-500">Phase 6 ships the sandbox adapter only — sandbox_only is enforced.</span>
        </div>
      )}

      <div className="grid gap-4">
        {providers.map((p) => (
          <div key={p.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Plug size={16} className="text-neutral-400" />
                <div>
                  <div className="text-sm font-semibold text-white flex items-center gap-2">
                    {p.name}
                    {p.sandbox_only && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-300">
                        <ShieldCheck size={10} /> sandbox only
                      </span>
                    )}
                    {!p.enabled && <span className="text-[10px] text-neutral-500">disabled</span>}
                  </div>
                  <div className="text-[11px] text-neutral-500">
                    {p.adapter_type} · {p.rate_limit_per_minute}/min · credential {p.has_credential ? "set" : "not set"}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="text-xs text-neutral-400 hover:text-white" onClick={() => handleSetCredential(p)}>
                  {p.has_credential ? "Rotate credential" : "Set credential"}
                </button>
                <button className="text-xs text-neutral-400 hover:text-white" onClick={() => handleToggleProvider(p)}>
                  {p.enabled ? "Disable" : "Enable"}
                </button>
                <button
                  className="text-xs text-sky-400 hover:text-sky-300"
                  onClick={() => { setShowActionForm(showActionForm === p.id ? null : p.id); setActionType("sandbox_action"); }}
                >
                  New action
                </button>
              </div>
            </div>

            {showActionForm === p.id && (
              <div className="mt-3 flex flex-wrap items-end gap-3 rounded-lg border border-white/10 bg-black/20 p-3">
                <label className="text-xs text-neutral-400 flex flex-col gap-1">
                  Action type
                  <input
                    className="bg-neutral-900 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white"
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                  />
                </label>
                <label className="text-xs text-neutral-400 flex flex-col gap-1 flex-1 min-w-56">
                  Payload (JSON)
                  <input
                    className="bg-neutral-900 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white font-mono"
                    value={actionPayload}
                    onChange={(e) => setActionPayload(e.target.value)}
                  />
                </label>
                <button className="button button-primary" onClick={() => handleCreateAction(p.id)}>Submit for approval</button>
              </div>
            )}
          </div>
        ))}
        {providers.length === 0 && !loading && (
          <div className="rounded-xl border border-dashed border-white/10 p-8 text-center text-sm text-neutral-500">
            No providers configured. Create a sandbox provider to exercise the approval → execute → audit pipeline.
          </div>
        )}
      </div>

      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Actions</h2>
        <div className="rounded-xl border border-white/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-white/5 text-[11px] uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="text-left px-4 py-2">Action</th>
                <th className="text-left px-4 py-2">Provider</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Actor</th>
                <th className="text-left px-4 py-2">Created</th>
                <th className="text-right px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {actions.map((a) => {
                const provider = providers.find((p) => p.id === a.provider_id);
                const expanded = expandedAction === a.id;
                return (
                  <Fragment key={a.id}>
                    <tr className="border-t border-white/5">
                      <td className="px-4 py-2.5">
                        <button className="flex items-center gap-1 text-left text-white hover:text-sky-300" onClick={() => toggleDetail(a)}>
                          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                          <span className="font-medium">{a.action_type}</span>
                        </button>
                        <div className="text-[10px] text-neutral-600 font-mono">{a.id.slice(0, 8)}… · hash {a.payload_hash.slice(0, 10)}…</div>
                      </td>
                      <td className="px-4 py-2.5 text-neutral-400">{provider?.name ?? a.provider_id.slice(0, 8)}</td>
                      <td className="px-4 py-2.5"><StatusBadge status={a.status} /></td>
                      <td className="px-4 py-2.5 text-neutral-400">{a.actor}</td>
                      <td className="px-4 py-2.5 text-neutral-500 text-xs">{new Date(a.created_at).toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-right">
                        <div className="inline-flex gap-2">
                          {a.status === "pending_approval" && (
                            <>
                              <button className="text-xs text-emerald-400 hover:text-emerald-300 inline-flex items-center gap-1" onClick={() => handleDecide(a, "approve")}>
                                <CheckCircle2 size={12} /> Approve
                              </button>
                              <button className="text-xs text-red-400 hover:text-red-300 inline-flex items-center gap-1" onClick={() => handleDecide(a, "reject")}>
                                <XCircle size={12} /> Reject
                              </button>
                            </>
                          )}
                          {(a.status === "pending_approval" || a.status === "approved") && (
                            <button className="text-xs text-neutral-400 hover:text-white" onClick={() => handleDecide(a, "cancel")}>Cancel</button>
                          )}
                          {a.status === "approved" && (
                            <button className="text-xs text-sky-400 hover:text-sky-300 inline-flex items-center gap-1" onClick={() => handleExecute(a)}>
                              <Play size={12} /> Execute
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="border-t border-white/5 bg-black/20">
                        <td colSpan={6} className="px-4 py-3">
                          {actionDetail === null ? (
                            <LoaderCircle size={14} className="animate-spin text-neutral-500" />
                          ) : (
                            <div className="grid md:grid-cols-2 gap-4 text-xs">
                              <div>
                                <div className="text-neutral-500 mb-1">Event timeline (immutable)</div>
                                <ul className="space-y-1">
                                  {actionDetail.events.map((e) => (
                                    <li key={e.id} className="text-neutral-300">
                                      <span className="text-neutral-500">#{e.seq}</span> {e.event_type} · {e.actor} · {new Date(e.created_at).toLocaleTimeString()}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                              <div>
                                <div className="text-neutral-500 mb-1">Call attempts</div>
                                <ul className="space-y-1">
                                  {actionDetail.calls.map((c) => (
                                    <li key={c.id} className="text-neutral-300">
                                      #{c.attempt} {c.mode} → {c.status} ({c.response_status ?? "-"}, {c.latency_ms ?? "-"}ms)
                                      {c.error && <span className="text-red-400"> · {c.error}</span>}
                                    </li>
                                  ))}
                                  {actionDetail.calls.length === 0 && <li className="text-neutral-600">No attempts yet</li>}
                                </ul>
                                {a.result && (
                                  <pre className="mt-2 rounded bg-black/40 p-2 text-[10px] text-neutral-400 overflow-auto">{JSON.stringify(a.result, null, 2)}</pre>
                                )}
                                {a.error && <div className="mt-1 text-red-400">{a.error}</div>}
                              </div>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
              {actions.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-neutral-500">No actions yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
