import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Database,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import {
  createGoal,
  createOpportunity,
  createProject,
  createResearchRecord,
  createStrategy,
  deleteGoal,
  deleteOpportunity,
  deleteProject,
  deleteResearchRecord,
  deleteStrategy,
  listGoals,
  listOpportunities,
  listResearchRecords,
  listStrategies,
  transitionOpportunity,
  transitionStrategy,
  updateGoal,
  updateOpportunity,
  updateProject,
  updateResearchRecord,
  updateStrategy,
} from "../lib/api";
import type {
  GrowthStrategy,
  Opportunity,
  OpportunityCategory,
  OpportunityEffort,
  OpportunityImpact,
  OpportunityStatus,
  Project,
  ProjectCategory,
  ProjectStatus,
  ResearchRecord,
  SourceType,
  StrategyGoal,
  StrategyStatus,
} from "../types";

type Resource = "projects" | "research" | "opportunities" | "strategies" | "goals";

type GoalRow = StrategyGoal & { strategyName: string };

type Editor =
  | { resource: "projects"; mode: "create" }
  | { resource: "projects"; mode: "edit"; record: Project }
  | { resource: "research"; mode: "create" }
  | { resource: "research"; mode: "edit"; record: ResearchRecord }
  | { resource: "opportunities"; mode: "create" }
  | { resource: "opportunities"; mode: "edit"; record: Opportunity }
  | { resource: "strategies"; mode: "create" }
  | { resource: "strategies"; mode: "edit"; record: GrowthStrategy }
  | { resource: "goals"; mode: "create" }
  | { resource: "goals"; mode: "edit"; record: GoalRow };

const CATEGORIES: ProjectCategory[] = ["mobile_app", "web_app", "saas", "ecommerce", "other"];
const PROJECT_STATUSES: ProjectStatus[] = ["active", "paused", "archived"];
const SOURCE_TYPES: SourceType[] = [
  "user_interview",
  "app_review",
  "competitor_analysis",
  "analytics",
  "market_report",
  "manual_observation",
];
const OPP_CATEGORIES: OpportunityCategory[] = [
  "acquisition",
  "activation",
  "retention",
  "referral",
  "revenue",
  "experimentation",
];
const IMPACTS: OpportunityImpact[] = ["low", "medium", "high", "critical"];
const EFFORTS: OpportunityEffort[] = ["low", "medium", "high"];
const GOAL_STATUSES = ["pending", "on_track", "at_risk", "behind", "achieved", "abandoned"] as const;

const NEXT_OPPORTUNITY: Record<OpportunityStatus, OpportunityStatus[]> = {
  draft: ["in_review", "archived"],
  in_review: ["approved", "rejected", "draft", "archived"],
  approved: ["archived"],
  rejected: ["draft", "archived"],
  archived: [],
};

const NEXT_STRATEGY: Record<StrategyStatus, StrategyStatus[]> = {
  draft: ["in_review", "archived"],
  in_review: ["approved", "draft", "archived"],
  approved: ["active", "draft", "archived"],
  active: ["completed", "in_review", "archived"],
  completed: ["archived"],
  archived: ["draft"],
};

const TABS: { id: Resource; label: string }[] = [
  { id: "projects", label: "Projects" },
  { id: "research", label: "Research" },
  { id: "opportunities", label: "Opportunities" },
  { id: "strategies", label: "Strategies" },
  { id: "goals", label: "Goals" },
];

function labelize(value: string) {
  return value.replace(/_/g, " ");
}

function text(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function AdminConsole({
  projects,
  activeProjectId,
  onSelectProject,
  onProjectCreated,
  onProjectUpdated,
  onProjectDeleted,
}: {
  projects: Project[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
  onProjectCreated: (project: Project) => void;
  onProjectUpdated: (project: Project) => void;
  onProjectDeleted: (id: string) => void;
}) {
  const [tab, setTab] = useState<Resource>("projects");
  const [query, setQuery] = useState("");
  const [research, setResearch] = useState<ResearchRecord[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [strategies, setStrategies] = useState<GrowthStrategy[]>([]);
  const [goals, setGoals] = useState<GoalRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const project = projects.find((item) => item.id === activeProjectId) ?? null;

  const reload = useCallback(() => setReloadToken((value) => value + 1), []);

  useEffect(() => {
    if (!activeProjectId) {
      setResearch([]);
      setOpportunities([]);
      setStrategies([]);
      setGoals([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    void (async () => {
      try {
        const [researchResult, opportunityResult, strategyResult] = await Promise.all([
          listResearchRecords(activeProjectId, { limit: 200 }),
          listOpportunities(activeProjectId, { limit: 200 }),
          listStrategies(activeProjectId, { limit: 200 }),
        ]);
        const goalGroups = await Promise.all(
          strategyResult.items.map(async (strategy) => {
            const items = await listGoals(activeProjectId, strategy.id);
            return items.map((goal) => ({ ...goal, strategyName: strategy.name }));
          }),
        );
        if (cancelled) return;
        setResearch(researchResult.items);
        setOpportunities(opportunityResult.items);
        setStrategies(strategyResult.items);
        setGoals(goalGroups.flat());
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Could not load workspace data.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeProjectId, reloadToken]);

  const needle = query.trim().toLowerCase();
  const matches = (values: Array<string | number | null | undefined>) =>
    !needle || values.some((value) => String(value ?? "").toLowerCase().includes(needle));

  const visibleProjects = projects.filter((item) =>
    matches([item.name, item.slug, item.status, item.category, item.description]),
  );
  const visibleResearch = research.filter((item) =>
    matches([item.title, item.source_type, item.observation_summary, item.source_name]),
  );
  const visibleOpportunities = opportunities.filter((item) =>
    matches([item.title, item.status, item.category, item.priority, item.problem_statement]),
  );
  const visibleStrategies = strategies.filter((item) =>
    matches([item.name, item.status, item.time_horizon, item.strategic_vision]),
  );
  const visibleGoals = goals.filter((item) =>
    matches([item.name, item.metric_name, item.status, item.strategyName]),
  );

  const counts: Record<Resource, number> = {
    projects: projects.length,
    research: research.length,
    opportunities: opportunities.length,
    strategies: strategies.length,
    goals: goals.length,
  };

  const needsProject = tab !== "projects" && !project;

  async function removeRow(resource: Resource, id: string, strategyId?: string) {
    if (!window.confirm("Delete this record? This cannot be undone.")) return;
    if (resource === "projects") {
      await deleteProject(id);
      onProjectDeleted(id);
      return;
    }
    if (!activeProjectId) return;
    if (resource === "research") await deleteResearchRecord(activeProjectId, id);
    if (resource === "opportunities") await deleteOpportunity(activeProjectId, id);
    if (resource === "strategies") await deleteStrategy(activeProjectId, id);
    if (resource === "goals" && strategyId) await deleteGoal(activeProjectId, strategyId, id);
    reload();
  }

  return (
    <div className="admin-console">
      <div className="page-heading flex items-end justify-between">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> CONTROL PANEL</div>
          <h1>Admin<span className="heading-period">.</span></h1>
          <p className="page-subtitle">Search, edit, and delete the records this workspace already stores.</p>
        </div>
        <button className="button button-secondary" type="button" onClick={reload} disabled={loading || !activeProjectId}>
          <RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh data
        </button>
      </div>

      <section className="admin-metrics" aria-label="Record counts">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`admin-metric panel ${tab === item.id ? "is-active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            <span>{item.label}</span>
            <strong>{item.id === "projects" || project ? counts[item.id] : "—"}</strong>
          </button>
        ))}
      </section>

      <section className="panel admin-board">
        <div className="admin-toolbar">
          <div className="admin-tabs" role="tablist" aria-label="Data collections">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={`filter-pill ${tab === item.id ? "active" : ""}`}
                onClick={() => setTab(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="search-input-wrap admin-search">
            <Search size={14} />
            <input
              className="search-input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={`Search ${tab}`}
              aria-label={`Search ${tab}`}
            />
          </label>
          {tab !== "projects" && (
            <select
              className="category-select"
              value={activeProjectId}
              onChange={(event) => onSelectProject(event.target.value)}
              aria-label="Project"
            >
              <option value="">Select a project</option>
              {projects.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          )}
          <button
            className="button button-primary"
            type="button"
            disabled={needsProject || (tab === "goals" && strategies.length === 0)}
            onClick={() => setEditor({ resource: tab, mode: "create" } as Editor)}
          >
            <Plus size={14} /> New
          </button>
        </div>

        {loadError && <div className="admin-banner" role="alert">{loadError}</div>}

        {needsProject ? (
          <EmptyState
            icon={Database}
            title="Choose a project"
            detail="Research, opportunities, strategies, and goals belong to a project. Create one from the Projects tab, then select it here."
          />
        ) : loading && tab !== "projects" ? (
          <EmptyState icon={LoaderCircle} title="Loading records" detail="Pulling the latest data for this project." spin />
        ) : tab === "projects" ? (
          <DataTable
            columns={["Name", "Category", "Status", "Slug"]}
            rows={visibleProjects.map((item) => ({
              id: item.id,
              cells: [item.name, labelize(item.category), item.status, item.slug],
            }))}
            onEdit={(id) => {
              const record = projects.find((item) => item.id === id);
              if (record) setEditor({ resource: "projects", mode: "edit", record });
            }}
            emptyTitle={projects.length === 0 ? "No projects yet" : "Nothing matches"}
            emptyDetail={projects.length === 0 ? "Create a project to start organizing growth data." : "Adjust the search, or create a record."}
            onDelete={(id) => void removeRow("projects", id).catch((err) => setLoadError(messageOf(err)))}
          />
        ) : tab === "research" ? (
          <DataTable
            columns={["Title", "Source", "Summary"]}
            rows={visibleResearch.map((item) => ({
              id: item.id,
              cells: [item.title, labelize(item.source_type), item.observation_summary],
            }))}
            onEdit={(id) => {
              const record = research.find((item) => item.id === id);
              if (record) setEditor({ resource: "research", mode: "edit", record });
            }}
            onDelete={(id) => void removeRow("research", id).catch((err) => setLoadError(messageOf(err)))}
          />
        ) : tab === "opportunities" ? (
          <DataTable
            columns={["Title", "Status", "Priority", "Category"]}
            rows={visibleOpportunities.map((item) => ({
              id: item.id,
              cells: [item.title, labelize(item.status), labelize(item.priority), labelize(item.category)],
            }))}
            onEdit={(id) => {
              const record = opportunities.find((item) => item.id === id);
              if (record) setEditor({ resource: "opportunities", mode: "edit", record });
            }}
            onDelete={(id) => void removeRow("opportunities", id).catch((err) => setLoadError(messageOf(err)))}
          />
        ) : tab === "strategies" ? (
          <DataTable
            columns={["Name", "Status", "Horizon", "Audience"]}
            rows={visibleStrategies.map((item) => ({
              id: item.id,
              cells: [item.name, labelize(item.status), item.time_horizon, item.target_audience],
            }))}
            onEdit={(id) => {
              const record = strategies.find((item) => item.id === id);
              if (record) setEditor({ resource: "strategies", mode: "edit", record });
            }}
            onDelete={(id) => void removeRow("strategies", id).catch((err) => setLoadError(messageOf(err)))}
          />
        ) : (
          <DataTable
            columns={["Goal", "Strategy", "Metric", "Current", "Target", "Status"]}
            rows={visibleGoals.map((item) => ({
              id: item.id,
              cells: [
                item.name,
                item.strategyName,
                `${item.metric_name} (${item.metric_unit})`,
                text(item.current_value),
                text(item.target_value),
                labelize(item.status),
              ],
            }))}
            emptyTitle={strategies.length === 0 ? "Add a strategy first" : "No goals yet"}
            emptyDetail={strategies.length === 0 ? "Goals are stored on a strategy." : "Create a measurable goal for this project."}
            onEdit={(id) => {
              const record = goals.find((item) => item.id === id);
              if (record) setEditor({ resource: "goals", mode: "edit", record });
            }}
            onDelete={(id) => {
              const record = goals.find((item) => item.id === id);
              if (!record) return;
              void removeRow("goals", id, record.strategy_id).catch((err) => setLoadError(messageOf(err)));
            }}
          />
        )}
      </section>

      {editor && (
        <RecordEditor
          editor={editor}
          projectId={activeProjectId}
          strategies={strategies}
          onClose={() => setEditor(null)}
          onSaved={(saved) => {
            if (editor.resource === "projects" && editor.mode === "create") onProjectCreated(saved as Project);
            if (editor.resource === "projects" && editor.mode === "edit") onProjectUpdated(saved as Project);
            if (editor.resource !== "projects") reload();
            setEditor(null);
          }}
        />
      )}
    </div>
  );
}

function DataTable({
  columns,
  rows,
  onEdit,
  onDelete,
  emptyTitle = "Nothing matches",
  emptyDetail = "Adjust the search, or create a record.",
}: {
  columns: string[];
  rows: { id: string; cells: string[] }[];
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  emptyTitle?: string;
  emptyDetail?: string;
}) {
  if (rows.length === 0) {
    return <EmptyState icon={Search} title={emptyTitle} detail={emptyDetail} />;
  }
  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            {columns.map((column) => <th key={column}>{column}</th>)}
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {row.cells.map((cell, index) => (
                <td key={`${row.id}-${index}`} title={cell}>{cell}</td>
              ))}
              <td className="admin-actions">
                <button type="button" className="icon-button" aria-label="Edit record" onClick={() => onEdit(row.id)}>
                  <Pencil size={14} />
                </button>
                <button type="button" className="icon-button" aria-label="Delete record" onClick={() => onDelete(row.id)}>
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
  detail,
  spin = false,
}: {
  icon: typeof Database;
  title: string;
  detail: string;
  spin?: boolean;
}) {
  return (
    <div className="admin-empty">
      <Icon size={18} className={spin ? "spin" : ""} />
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function RecordEditor({
  editor,
  projectId,
  strategies,
  onClose,
  onSaved,
}: {
  editor: Editor;
  projectId: string;
  strategies: GrowthStrategy[];
  onClose: () => void;
  onSaved: (record: Project | ResearchRecord | Opportunity | GrowthStrategy | StrategyGoal) => void;
}) {
  const [form, setForm] = useState<Record<string, string>>(() => {
    const seeded = seedForm(editor);
    if (editor.resource === "goals" && editor.mode === "create" && !seeded.strategy_id) {
      seeded.strategy_id = strategies[0]?.id ?? "";
    }
    return seeded;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function setField(name: string, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const saved = await persist(editor, form, projectId);
      onSaved(saved);
    } catch (err) {
      setError(messageOf(err));
      setSaving(false);
    }
  }

  const resourceLabel: Record<Resource, string> = {
    projects: "project",
    research: "research record",
    opportunities: "opportunity",
    strategies: "strategy",
    goals: "goal",
  };
  const title = `${editor.mode === "create" ? "New" : "Edit"} ${resourceLabel[editor.resource]}`;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={title} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="modal-dialog admin-dialog">
        <div className="modal-header">
          <h3>{title}</h3>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close"><X size={14} /></button>
        </div>
        <form onSubmit={(event) => void onSubmit(event)}>
          {editor.resource === "projects" && (
            <>
              <Field label="Name" value={form.name} onChange={(value) => setField("name", value)} required />
              <SelectField label="Category" value={form.category} options={CATEGORIES} onChange={(value) => setField("category", value)} />
              {editor.mode === "edit" && (
                <SelectField label="Status" value={form.status} options={PROJECT_STATUSES} onChange={(value) => setField("status", value)} />
              )}
              <Field label="Target audience" value={form.target_audience} onChange={(value) => setField("target_audience", value)} />
              <Area label="Description" value={form.description} onChange={(value) => setField("description", value)} />
            </>
          )}
          {editor.resource === "research" && (
            <>
              <Field label="Title" value={form.title} onChange={(value) => setField("title", value)} required />
              <SelectField label="Source type" value={form.source_type} options={SOURCE_TYPES} onChange={(value) => setField("source_type", value)} />
              <Field label="Source name" value={form.source_name} onChange={(value) => setField("source_name", value)} />
              <Area label="Observation" value={form.observation_summary} onChange={(value) => setField("observation_summary", value)} required />
              <Area label="Interpretation" value={form.interpretation_notes} onChange={(value) => setField("interpretation_notes", value)} />
            </>
          )}
          {editor.resource === "opportunities" && (
            <>
              <Field label="Title" value={form.title} onChange={(value) => setField("title", value)} required />
              <SelectField label="Category" value={form.category} options={OPP_CATEGORIES} onChange={(value) => setField("category", value)} />
              <SelectField label="Impact" value={form.estimated_impact} options={IMPACTS} onChange={(value) => setField("estimated_impact", value)} />
              <SelectField label="Effort" value={form.estimated_effort} options={EFFORTS} onChange={(value) => setField("estimated_effort", value)} />
              <Area label="Problem" value={form.problem_statement} onChange={(value) => setField("problem_statement", value)} required />
              <Area label="Hypothesis" value={form.hypothesis} onChange={(value) => setField("hypothesis", value)} required />
              <Area label="Mechanism" value={form.proposed_mechanism} onChange={(value) => setField("proposed_mechanism", value)} required />
              <Field label="Target audience" value={form.target_audience} onChange={(value) => setField("target_audience", value)} required />
              {editor.mode === "edit" && (
                <>
                  <SelectField
                    label="Move status to"
                    value={form.status}
                    options={[editor.record.status, ...NEXT_OPPORTUNITY[editor.record.status]]}
                    onChange={(value) => setField("status", value)}
                  />
                  <Area label="Reason" value={form.reason} onChange={(value) => setField("reason", value)} />
                </>
              )}
            </>
          )}
          {editor.resource === "strategies" && (
            <>
              <Field label="Name" value={form.name} onChange={(value) => setField("name", value)} required />
              <Field label="Time horizon" value={form.time_horizon} onChange={(value) => setField("time_horizon", value)} required />
              <Field label="Currency" value={form.currency} onChange={(value) => setField("currency", value)} />
              <Field label="Budget" value={form.budget_envelope} onChange={(value) => setField("budget_envelope", value)} />
              <Field label="Target audience" value={form.target_audience} onChange={(value) => setField("target_audience", value)} required />
              <Area label="Vision" value={form.strategic_vision} onChange={(value) => setField("strategic_vision", value)} required />
              <Area label="Constraints" value={form.strategic_constraints} onChange={(value) => setField("strategic_constraints", value)} />
              {editor.mode === "edit" && (
                <>
                  <SelectField
                    label="Move status to"
                    value={form.status}
                    options={[editor.record.status, ...NEXT_STRATEGY[editor.record.status]]}
                    onChange={(value) => setField("status", value)}
                  />
                  <Area label="Reason" value={form.reason} onChange={(value) => setField("reason", value)} />
                </>
              )}
            </>
          )}
          {editor.resource === "goals" && (
            <>
              {editor.mode === "create" ? (
                <SelectField
                  label="Strategy"
                  value={form.strategy_id}
                  options={strategies.map((item) => item.id)}
                  labels={Object.fromEntries(strategies.map((item) => [item.id, item.name]))}
                  onChange={(value) => setField("strategy_id", value)}
                />
              ) : (
                <Field label="Strategy" value={editor.record.strategyName} onChange={() => undefined} />
              )}
              <Field label="Name" value={form.name} onChange={(value) => setField("name", value)} required />
              <Field label="Metric" value={form.metric_name} onChange={(value) => setField("metric_name", value)} required />
              <Field label="Unit" value={form.metric_unit} onChange={(value) => setField("metric_unit", value)} required />
              <Field label="Baseline" value={form.baseline_value} onChange={(value) => setField("baseline_value", value)} required />
              <Field label="Current" value={form.current_value} onChange={(value) => setField("current_value", value)} />
              <Field label="Target" value={form.target_value} onChange={(value) => setField("target_value", value)} required />
              <SelectField label="Status" value={form.status} options={[...GOAL_STATUSES]} onChange={(value) => setField("status", value)} />
            </>
          )}
          {error && <div className="admin-banner" role="alert">{error}</div>}
          <div className="form-actions">
            <button type="button" className="button button-secondary" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" className="button button-primary" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="form-group">
      <span className="form-label">{label}</span>
      <input className="form-input" value={value} required={required} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Area({
  label,
  value,
  onChange,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="form-group">
      <span className="form-label">{label}</span>
      <textarea className="form-textarea" rows={3} value={value} required={required} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  labels?: Record<string, string>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="form-group">
      <span className="form-label">{label}</span>
      <select className="form-select" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>{labels?.[option] ?? labelize(option)}</option>
        ))}
      </select>
    </label>
  );
}

function seedForm(editor: Editor): Record<string, string> {
  if (editor.resource === "projects" && editor.mode === "edit") {
    return {
      name: editor.record.name,
      category: editor.record.category,
      status: editor.record.status,
      target_audience: editor.record.target_audience ?? "",
      description: editor.record.description ?? "",
    };
  }
  if (editor.resource === "projects") {
    return { name: "", category: "web_app", status: "active", target_audience: "", description: "" };
  }
  if (editor.resource === "research" && editor.mode === "edit") {
    return {
      title: editor.record.title,
      source_type: editor.record.source_type,
      source_name: editor.record.source_name ?? "",
      observation_summary: editor.record.observation_summary,
      interpretation_notes: editor.record.interpretation_notes ?? "",
    };
  }
  if (editor.resource === "research") {
    return { title: "", source_type: "manual_observation", source_name: "", observation_summary: "", interpretation_notes: "" };
  }
  if (editor.resource === "opportunities" && editor.mode === "edit") {
    return {
      title: editor.record.title,
      category: editor.record.category,
      estimated_impact: editor.record.estimated_impact,
      estimated_effort: editor.record.estimated_effort,
      problem_statement: editor.record.problem_statement,
      hypothesis: editor.record.hypothesis,
      proposed_mechanism: editor.record.proposed_mechanism,
      target_audience: editor.record.target_audience,
      status: editor.record.status,
      reason: "",
    };
  }
  if (editor.resource === "opportunities") {
    return {
      title: "",
      category: "acquisition",
      estimated_impact: "medium",
      estimated_effort: "medium",
      problem_statement: "",
      hypothesis: "",
      proposed_mechanism: "",
      target_audience: "",
      status: "draft",
      reason: "",
    };
  }
  if (editor.resource === "strategies" && editor.mode === "edit") {
    return {
      name: editor.record.name,
      time_horizon: editor.record.time_horizon,
      currency: editor.record.currency,
      budget_envelope: editor.record.budget_envelope == null ? "" : String(editor.record.budget_envelope),
      target_audience: editor.record.target_audience,
      strategic_vision: editor.record.strategic_vision,
      strategic_constraints: editor.record.strategic_constraints ?? "",
      status: editor.record.status,
      reason: "",
    };
  }
  if (editor.resource === "strategies") {
    return {
      name: "",
      time_horizon: "",
      currency: "USD",
      budget_envelope: "",
      target_audience: "",
      strategic_vision: "",
      strategic_constraints: "",
      status: "draft",
      reason: "",
    };
  }
  if (editor.mode === "edit") {
    return {
      strategy_id: editor.record.strategy_id,
      name: editor.record.name,
      metric_name: editor.record.metric_name,
      metric_unit: editor.record.metric_unit,
      baseline_value: String(editor.record.baseline_value),
      current_value: String(editor.record.current_value),
      target_value: String(editor.record.target_value),
      status: editor.record.status,
    };
  }
  return {
    strategy_id: "",
    name: "",
    metric_name: "",
    metric_unit: "",
    baseline_value: "0",
    current_value: "0",
    target_value: "0",
    status: "pending",
  };
}

async function persist(editor: Editor, form: Record<string, string>, projectId: string) {
  const optional = (value: string) => value.trim() || undefined;
  if (editor.resource === "projects") {
    if (editor.mode === "create") {
      return createProject({
        name: form.name.trim(),
        category: form.category as ProjectCategory,
        description: optional(form.description),
        target_audience: optional(form.target_audience),
      });
    }
    return updateProject(editor.record.id, {
      name: form.name.trim(),
      category: form.category as ProjectCategory,
      status: form.status as ProjectStatus,
      description: form.description,
      target_audience: form.target_audience,
    });
  }
  if (!projectId) throw new Error("Select a project first.");
  if (editor.resource === "research") {
    const payload = {
      title: form.title.trim(),
      source_type: form.source_type as SourceType,
      source_name: optional(form.source_name),
      observation_summary: form.observation_summary.trim(),
      interpretation_notes: optional(form.interpretation_notes),
    };
    return editor.mode === "create"
      ? createResearchRecord(projectId, payload)
      : updateResearchRecord(projectId, editor.record.id, payload);
  }
  if (editor.resource === "opportunities") {
    const payload = {
      title: form.title.trim(),
      category: form.category as OpportunityCategory,
      estimated_impact: form.estimated_impact as OpportunityImpact,
      estimated_effort: form.estimated_effort as OpportunityEffort,
      problem_statement: form.problem_statement.trim(),
      hypothesis: form.hypothesis.trim(),
      proposed_mechanism: form.proposed_mechanism.trim(),
      target_audience: form.target_audience.trim(),
    };
    if (editor.mode === "create") return createOpportunity(projectId, payload);
    const updated = await updateOpportunity(projectId, editor.record.id, payload);
    if (form.status !== editor.record.status) {
      return transitionOpportunity(projectId, editor.record.id, {
        status: form.status as OpportunityStatus,
        reason: optional(form.reason),
      });
    }
    return updated;
  }
  if (editor.resource === "strategies") {
    const budget = form.budget_envelope.trim() ? Number(form.budget_envelope) : undefined;
    if (budget !== undefined && Number.isNaN(budget)) throw new Error("Budget must be a number.");
    const payload = {
      name: form.name.trim(),
      time_horizon: form.time_horizon.trim(),
      currency: optional(form.currency),
      budget_envelope: budget,
      target_audience: form.target_audience.trim(),
      strategic_vision: form.strategic_vision.trim(),
      strategic_constraints: optional(form.strategic_constraints),
    };
    if (editor.mode === "create") return createStrategy(projectId, payload);
    const updated = await updateStrategy(projectId, editor.record.id, payload);
    if (form.status !== editor.record.status) {
      return transitionStrategy(projectId, editor.record.id, {
        status: form.status as StrategyStatus,
        reason: optional(form.reason),
      });
    }
    return updated;
  }
  const baseline = Number(form.baseline_value);
  const current = Number(form.current_value);
  const target = Number(form.target_value);
  if ([baseline, current, target].some((value) => Number.isNaN(value))) {
    throw new Error("Baseline, current, and target must be numbers.");
  }
  const goalPayload = {
    name: form.name.trim(),
    metric_name: form.metric_name.trim(),
    metric_unit: form.metric_unit.trim(),
    baseline_value: baseline,
    current_value: current,
    target_value: target,
    status: form.status as StrategyGoal["status"],
  };
  const strategyId = editor.mode === "edit" ? editor.record.strategy_id : form.strategy_id;
  if (!strategyId) throw new Error("Choose a strategy for this goal.");
  return editor.mode === "create"
    ? createGoal(projectId, strategyId, goalPayload)
    : updateGoal(projectId, strategyId, editor.record.id, goalPayload);
}

function messageOf(err: unknown) {
  return err instanceof Error ? err.message : "The request failed.";
}
