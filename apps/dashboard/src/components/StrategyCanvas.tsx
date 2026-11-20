import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  Target,
  Trash2,
  X,
} from "lucide-react";
import {
  createStrategy,
  deleteStrategy,
  listStrategies,
  transitionStrategy,
} from "../lib/api";
import type {
  GrowthStrategy,
  GrowthStrategyCreateInput,
  GrowthStrategyTransitionInput,
  Project,
  StrategyStatus,
} from "../types";
import { StrategyDrawer } from "./StrategyDrawer";
import { StrategyTransitionModal } from "./StrategyTransitionModal";

// ─── Constants ───────────────────────────────────────────────────────────────

const TIME_HORIZONS = [
  { value: "short_term", label: "Short-term (< 3 mo)" },
  { value: "medium_term", label: "Medium-term (3–12 mo)" },
  { value: "long_term", label: "Long-term (1–3 yr)" },
  { value: "multi_year", label: "Multi-year (3+ yr)" },
];

const STATUS_FILTERS: { value: StrategyStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "in_review", label: "In Review" },
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
];

const STATUS_TONE: Record<StrategyStatus, string> = {
  draft: "neutral",
  in_review: "amber",
  approved: "emerald",
  active: "emerald",
  completed: "sky",
  archived: "neutral",
};

const STATUS_LABEL: Record<StrategyStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  approved: "Approved",
  active: "Active",
  completed: "Completed",
  archived: "Archived",
};

// ─── Props ───────────────────────────────────────────────────────────────────

interface StrategyCanvasProps {
  projects: Project[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function StrategyCanvas({ projects, activeProjectId, onSelectProject }: StrategyCanvasProps) {
  const [strategies, setStrategies] = useState<GrowthStrategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<StrategyStatus | "all">("all");
  const [horizonFilter, setHorizonFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Create modal state
  const [createOpen, setCreateOpen] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<Partial<GrowthStrategyCreateInput>>({});

  // Drawer & transition state
  const [selectedStrategy, setSelectedStrategy] = useState<GrowthStrategy | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [transitionTarget, setTransitionTarget] = useState<GrowthStrategy | null>(null);
  const [transitionSubmitting, setTransitionSubmitting] = useState(false);

  // Delete confirm
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const projectId = activeProjectId || (projects[0]?.id ?? "");

  // ── Data loading ────────────────────────────────────────────────────────────

  const loadStrategies = useCallback(async (silent = false) => {
    if (!projectId) return;
    silent ? setRefreshing(true) : setLoading(true);
    setError(null);
    try {
      const res = await listStrategies(projectId);
      setStrategies(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load strategies.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [projectId]);

  useEffect(() => {
    setStrategies([]);
    setStatusFilter("all");
    setHorizonFilter("all");
    setSearchQuery("");
    void loadStrategies();
  }, [loadStrategies]);

  // ── Filtering ───────────────────────────────────────────────────────────────

  const filtered = strategies.filter((s) => {
    if (statusFilter !== "all" && s.status !== statusFilter) return false;
    if (horizonFilter !== "all" && s.time_horizon !== horizonFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        s.name.toLowerCase().includes(q) ||
        (s.description ?? "").toLowerCase().includes(q) ||
        s.strategic_vision.toLowerCase().includes(q) ||
        s.target_audience.toLowerCase().includes(q)
      );
    }
    return true;
  });

  // ── Stats ───────────────────────────────────────────────────────────────────

  const total = strategies.length;
  const active = strategies.filter((s) => s.status === "active").length;
  const approved = strategies.filter((s) => s.status === "approved").length;

  // ── Create strategy ─────────────────────────────────────────────────────────

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    const { name, strategic_vision, target_audience, time_horizon } = createForm;
    if (!name?.trim()) { setCreateError("Strategy name is required."); return; }
    if (!strategic_vision?.trim()) { setCreateError("Strategic vision is required."); return; }
    if (!target_audience?.trim()) { setCreateError("Target audience is required."); return; }
    if (!time_horizon) { setCreateError("Time horizon is required."); return; }
    setCreateSubmitting(true);
    try {
      const created = await createStrategy(projectId, {
        name: name.trim(),
        strategic_vision: strategic_vision.trim(),
        target_audience: target_audience.trim(),
        time_horizon,
        description: createForm.description?.trim() || undefined,
        strategic_constraints: createForm.strategic_constraints?.trim() || undefined,
        budget_envelope: createForm.budget_envelope ?? undefined,
        currency: createForm.currency?.trim() || undefined,
      });
      setStrategies((prev) => [created, ...prev]);
      setCreateOpen(false);
      setCreateForm({});
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create strategy.");
    } finally {
      setCreateSubmitting(false);
    }
  };

  // ── Transition ──────────────────────────────────────────────────────────────

  const handleTransition = async (targetStatus: StrategyStatus, reason?: string) => {
    if (!transitionTarget) return;
    setTransitionSubmitting(true);
    try {
      const payload: GrowthStrategyTransitionInput = { status: targetStatus, reason };
      const updated = await transitionStrategy(transitionTarget.project_id, transitionTarget.id, payload);
      setStrategies((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      if (selectedStrategy?.id === updated.id) setSelectedStrategy(updated);
      setTransitionTarget(null);
    } finally {
      setTransitionSubmitting(false);
    }
  };

  // ── Delete ──────────────────────────────────────────────────────────────────

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteStrategy(projectId, id);
      setStrategies((prev) => prev.filter((s) => s.id !== id));
      if (selectedStrategy?.id === id) setDrawerOpen(false);
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const activeProject = projects.find((p) => p.id === projectId);

  return (
    <div className="strategy-canvas">
      {/* Page heading */}
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> PHASE 5</div>
          <h1>Strategy &amp; Goals<span className="heading-period">.</span></h1>
          <p className="page-subtitle">Define growth strategies, set measurable goals, and link opportunities to execution plans.</p>
        </div>

        {/* Project selector */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div className="project-selector" style={{ position: "relative" }}>
            <select
              className="form-input"
              style={{ paddingRight: 28, appearance: "none", cursor: "pointer", fontSize: 13 }}
              value={projectId}
              onChange={(e) => onSelectProject(e.target.value)}
              aria-label="Select project"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <ChevronDown size={13} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--color-muted, #6b7280)" }} />
          </div>
          <button
            className="icon-button refresh-button"
            onClick={() => void loadStrategies(true)}
            disabled={refreshing}
            aria-label="Refresh strategies"
          >
            <RefreshCw size={14} className={refreshing ? "spin" : ""} />
          </button>
          <button
            className="btn btn-primary"
            onClick={() => { setCreateForm({}); setCreateError(null); setCreateOpen(true); }}
          >
            <Plus size={14} /> New strategy
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        {[
          { label: "Total Strategies", value: total },
          { label: "Active", value: active },
          { label: "Approved", value: approved },
        ].map(({ label, value }) => (
          <div key={label} className="panel" style={{ padding: "10px 16px", borderRadius: 8, minWidth: 120 }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.08em", color: "var(--color-muted, #6b7280)" }}>{label.toUpperCase()}</div>
            <div style={{ fontSize: 22, fontWeight: 700, marginTop: 2 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Error banner */}
      {error && (
        <div className="workspace-alert" role="alert" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertCircle size={15} /><span>{error}</span>
          </div>
          <button className="icon-button" onClick={() => setError(null)} aria-label="Dismiss"><X size={13} /></button>
        </div>
      )}

      {/* Filter toolbar */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        {/* Status filter chips */}
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {STATUS_FILTERS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value)}
              className={`filter-chip ${statusFilter === value ? "active" : ""}`}
              style={{
                fontSize: 12,
                padding: "4px 10px",
                borderRadius: 20,
                border: `1px solid ${statusFilter === value ? "rgba(99,102,241,0.7)" : "rgba(255,255,255,0.1)"}`,
                background: statusFilter === value ? "rgba(99,102,241,0.15)" : "transparent",
                color: statusFilter === value ? "#fff" : "var(--color-muted, #6b7280)",
                cursor: "pointer",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Time horizon filter */}
        <select
          className="form-input"
          style={{ fontSize: 12, padding: "4px 10px", height: "auto" }}
          value={horizonFilter}
          onChange={(e) => setHorizonFilter(e.target.value)}
          aria-label="Filter by time horizon"
        >
          <option value="all">All horizons</option>
          {TIME_HORIZONS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>

        {/* Search */}
        <div style={{ position: "relative", flex: 1, minWidth: 160 }}>
          <Search size={13} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--color-muted, #6b7280)", pointerEvents: "none" }} />
          <input
            type="text"
            className="form-input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search strategies…"
            style={{ paddingLeft: 30, fontSize: 12 }}
          />
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: "48px 0", color: "var(--color-muted, #6b7280)" }}>
          <LoaderCircle size={22} className="spin" />
        </div>
      )}

      {/* Empty state */}
      {!loading && strategies.length === 0 && !error && (
        <section className="empty-page panel" style={{ marginTop: 20 }}>
          <div className="empty-page-icon"><Target size={22} strokeWidth={1.6} /></div>
          <span className="panel-kicker">STRATEGY & GOALS</span>
          <h2>No strategies yet</h2>
          <p>
            {activeProject ? `Create the first growth strategy for "${activeProject.name}".` : "Select a project and create your first strategy."}
          </p>
          <button className="btn btn-primary" onClick={() => { setCreateForm({}); setCreateError(null); setCreateOpen(true); }}>
            <Plus size={14} /> New strategy
          </button>
        </section>
      )}

      {/* Empty filter result */}
      {!loading && strategies.length > 0 && filtered.length === 0 && (
        <div style={{ color: "var(--color-muted, #6b7280)", fontSize: 13, padding: "24px 0" }}>
          No strategies match the current filters.{" "}
          <button className="btn btn-ghost" style={{ fontSize: 12, padding: "2px 8px" }} onClick={() => { setStatusFilter("all"); setHorizonFilter("all"); setSearchQuery(""); }}>
            Clear filters
          </button>
        </div>
      )}

      {/* Strategy cards grid */}
      {!loading && filtered.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 14 }}>
          {filtered.map((strategy) => (
            <StrategyCard
              key={strategy.id}
              strategy={strategy}
              deletingId={deletingId}
              confirmDeleteId={confirmDeleteId}
              onView={() => { setSelectedStrategy(strategy); setDrawerOpen(true); }}
              onTransition={() => setTransitionTarget(strategy)}
              onDeleteRequest={() => setConfirmDeleteId(strategy.id)}
              onDeleteConfirm={() => void handleDelete(strategy.id)}
              onDeleteCancel={() => setConfirmDeleteId(null)}
            />
          ))}
        </div>
      )}

      {/* Create Strategy modal */}
      {createOpen && (
        <div
          className="modal-overlay"
          onClick={(e) => { if (e.target === e.currentTarget && !createSubmitting) { setCreateOpen(false); } }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-strategy-title"
        >
          <div className="modal-panel" style={{ maxWidth: 560 }}>
            <div className="modal-header">
              <div>
                <div className="eyebrow"><span className="eyebrow-line" /> NEW STRATEGY</div>
                <h2 id="create-strategy-title">Create growth strategy</h2>
              </div>
              <button className="icon-button" onClick={() => setCreateOpen(false)} disabled={createSubmitting} aria-label="Close">
                <X size={16} />
              </button>
            </div>

            {createError && (
              <div className="modal-error" role="alert"><AlertCircle size={14} /><span>{createError}</span></div>
            )}

            <form onSubmit={(e) => void handleCreate(e)} className="modal-form">
              <div className="form-group">
                <label htmlFor="cs-name">Strategy name *</label>
                <input id="cs-name" type="text" className="form-input" value={createForm.name ?? ""} onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value.slice(0, 200) }))} placeholder="e.g. Accelerate SMB Acquisition" required />
              </div>
              <div className="form-group">
                <label htmlFor="cs-vision">Strategic vision *</label>
                <textarea id="cs-vision" className="form-input" value={createForm.strategic_vision ?? ""} onChange={(e) => setCreateForm((f) => ({ ...f, strategic_vision: e.target.value.slice(0, 1000) }))} placeholder="Describe the desired future state this strategy creates" rows={3} required />
              </div>
              <div className="form-group">
                <label htmlFor="cs-audience">Target audience *</label>
                <input id="cs-audience" type="text" className="form-input" value={createForm.target_audience ?? ""} onChange={(e) => setCreateForm((f) => ({ ...f, target_audience: e.target.value.slice(0, 500) }))} placeholder="e.g. SMB founders, 10–50 employees" required />
              </div>
              <div className="form-row">
                <div className="form-group" style={{ flex: 1 }}>
                  <label htmlFor="cs-horizon">Time horizon *</label>
                  <select id="cs-horizon" className="form-input" value={createForm.time_horizon ?? ""} onChange={(e) => setCreateForm((f) => ({ ...f, time_horizon: e.target.value }))} required>
                    <option value="" disabled>Select…</option>
                    {TIME_HORIZONS.map(({ value, label }) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group" style={{ flex: 1 }}>
                  <label htmlFor="cs-budget">Budget envelope</label>
                  <input id="cs-budget" type="number" className="form-input" value={createForm.budget_envelope ?? ""} onChange={(e) => setCreateForm((f) => ({ ...f, budget_envelope: e.target.value ? parseFloat(e.target.value) : undefined }))} placeholder="Optional" step="any" min="0" />
                </div>
                <div className="form-group" style={{ flex: 1 }}>
                  <label htmlFor="cs-currency">Currency</label>
                  <input id="cs-currency" type="text" className="form-input" value={createForm.currency ?? ""} onChange={(e) => setCreateForm((f) => ({ ...f, currency: e.target.value.slice(0, 10) }))} placeholder="USD" maxLength={10} />
                </div>
              </div>
              <div className="form-group">
                <label htmlFor="cs-desc">Description</label>
                <textarea id="cs-desc" className="form-input" value={createForm.description ?? ""} onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value.slice(0, 1000) }))} placeholder="Optional summary" rows={2} />
              </div>
              <div className="form-group">
                <label htmlFor="cs-constraints">Constraints</label>
                <textarea id="cs-constraints" className="form-input" value={createForm.strategic_constraints ?? ""} onChange={(e) => setCreateForm((f) => ({ ...f, strategic_constraints: e.target.value.slice(0, 1000) }))} placeholder="Limitations, risks, guardrails…" rows={2} />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setCreateOpen(false)} disabled={createSubmitting}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={createSubmitting}>
                  {createSubmitting ? <><LoaderCircle size={14} className="spin" /> Creating…</> : "Create strategy"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Strategy Drawer */}
      <StrategyDrawer
        strategy={selectedStrategy}
        isOpen={drawerOpen}
        projects={projects}
        onClose={() => setDrawerOpen(false)}
        onTransition={(s) => { setTransitionTarget(s); }}
      />

      {/* Transition modal */}
      {transitionTarget && (
        <StrategyTransitionModal
          strategy={transitionTarget}
          isOpen={!!transitionTarget}
          onClose={() => setTransitionTarget(null)}
          onSubmit={async (targetStatus, reason) => {
            setTransitionSubmitting(true);
            await handleTransition(targetStatus, reason);
            setTransitionSubmitting(false);
          }}
        />
      )}
      {transitionSubmitting && null /* suppress unused warning */}
    </div>
  );
}

// ─── Strategy card ────────────────────────────────────────────────────────────

interface StrategyCardProps {
  strategy: GrowthStrategy;
  deletingId: string | null;
  confirmDeleteId: string | null;
  onView: () => void;
  onTransition: () => void;
  onDeleteRequest: () => void;
  onDeleteConfirm: () => void;
  onDeleteCancel: () => void;
}

function StrategyCard({
  strategy,
  deletingId,
  confirmDeleteId,
  onView,
  onTransition,
  onDeleteRequest,
  onDeleteConfirm,
  onDeleteCancel,
}: StrategyCardProps) {
  const isDeleting = deletingId === strategy.id;
  const isConfirming = confirmDeleteId === strategy.id;
  const canDelete = strategy.status === "draft";

  const horizonLabel = TIME_HORIZONS.find((h) => h.value === strategy.time_horizon)?.label ?? strategy.time_horizon;

  return (
    <div className="panel" style={{ padding: "16px", borderRadius: 10, display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Card header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
            <span className={`status-badge ${STATUS_TONE[strategy.status]}`} style={{ fontSize: 10 }}>
              <span className="status-dot" />{STATUS_LABEL[strategy.status]}
            </span>
            <span style={{ fontSize: 10, color: "var(--color-muted, #6b7280)", background: "rgba(255,255,255,0.05)", borderRadius: 10, padding: "1px 7px" }}>
              {horizonLabel}
            </span>
          </div>
          <div style={{ fontWeight: 700, fontSize: 14, lineHeight: 1.3 }}>{strategy.name}</div>
        </div>
      </div>

      {/* Vision excerpt */}
      <div style={{ fontSize: 12, color: "var(--color-muted, #6b7280)", lineHeight: 1.5, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
        {strategy.strategic_vision}
      </div>

      {/* Audience chip */}
      {strategy.target_audience && (
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 10, background: "rgba(255,255,255,0.05)", borderRadius: 10, padding: "2px 8px", color: "var(--color-muted, #6b7280)" }}>
            👥 {strategy.target_audience.length > 50 ? strategy.target_audience.slice(0, 50) + "…" : strategy.target_audience}
          </span>
        </div>
      )}

      {/* Budget */}
      {strategy.budget_envelope != null && (
        <div style={{ fontSize: 11, color: "var(--color-muted, #6b7280)" }}>
          Budget: {strategy.budget_envelope.toLocaleString()} {strategy.currency}
        </div>
      )}

      {/* Actions */}
      {isConfirming ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", background: "rgba(244,63,94,0.1)", borderRadius: 6 }}>
          <span style={{ fontSize: 12, flex: 1 }}>Delete this strategy?</span>
          <button className="btn btn-ghost" style={{ fontSize: 11, padding: "3px 8px", color: "var(--color-rose, #f43f5e)" }} onClick={onDeleteConfirm} disabled={isDeleting}>
            {isDeleting ? <LoaderCircle size={12} className="spin" /> : "Delete"}
          </button>
          <button className="btn btn-ghost" style={{ fontSize: 11, padding: "3px 8px" }} onClick={onDeleteCancel}>
            Cancel
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", gap: 6, marginTop: 2 }}>
          <button className="btn btn-ghost" style={{ flex: 1, fontSize: 12, padding: "5px 0", justifyContent: "center" }} onClick={onView}>
            View details
          </button>
          <button
            className="btn btn-ghost"
            style={{ fontSize: 12, padding: "5px 10px" }}
            onClick={onTransition}
            title="Manage lifecycle"
          >
            Transition
          </button>
          {canDelete && (
            <button
              className="icon-button"
              onClick={onDeleteRequest}
              disabled={isDeleting}
              title="Delete strategy"
              style={{ color: "var(--color-rose, #f43f5e)" }}
            >
              {isDeleting ? <LoaderCircle size={13} className="spin" /> : <Trash2 size={13} />}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
