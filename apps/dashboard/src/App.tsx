import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  Calendar,
  ChevronDown,
  CircleHelp,
  Command,
  Database,
  ExternalLink,
  LayoutDashboard,
  LoaderCircle,
  Pencil,
  Plus,
  Radio,
  RefreshCw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  WifiOff,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  createProject,
  deleteProject,
  getApiBaseUrl,
  getHealth,
  getSystemInfo,
  listProjects,
  updateProject,
} from "./lib/api";
import type {
  ComponentHealth,
  HealthResponse,
  Project,
  ProjectCategory,
  ProjectCreateInput,
  ProjectStatus,
  ProjectUpdateInput,
  SystemInfo,
} from "./types";

type Page = "Overview" | "Projects" | "Agent Activity" | "Settings";
type Connection =
  | { state: "loading" }
  | { state: "offline"; checkedAt: Date }
  | { state: "online"; health: HealthResponse; system?: SystemInfo; checkedAt: Date };

const navigation: { label: Page; icon: LucideIcon }[] = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Projects", icon: Command },
  { label: "Agent Activity", icon: Activity },
];

function App() {
  const [page, setPage] = useState<Page>("Overview");
  const [connection, setConnection] = useState<Connection>({ state: "loading" });
  const [refreshing, setRefreshing] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const result = await listProjects();
      setProjects(result.items);
      setErrorBanner(null);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    const [healthResult, systemResult] = await Promise.allSettled([getHealth(), getSystemInfo()]);
    const checkedAt = new Date();
    if (healthResult.status === "fulfilled") {
      setConnection({
        state: "online",
        health: healthResult.value,
        system: systemResult.status === "fulfilled" ? systemResult.value : undefined,
        checkedAt,
      });
    } else {
      setConnection({ state: "offline", checkedAt });
    }
    setRefreshing(false);
    void fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const handleProjectUpdated = (updated: Project) => {
    setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  };

  const title = page === "Agent Activity" ? "Agent activity" : page;

  return (
    <div className="app-shell min-h-screen bg-canvas text-white">
      <aside className="sidebar flex flex-col">
        <div className="brand-lockup">
          <div className="brand-mark"><Sparkles size={18} strokeWidth={2.2} /></div>
          <div className="brand-copy">
            <span className="brand-name">growth<span className="brand-dot">.</span></span>
            <span className="brand-caption">AUTONOMOUS WORKSPACE</span>
          </div>
        </div>

        <div className="workspace-switcher" aria-label="Current workspace">
          <div className="workspace-avatar">U</div>
          <div className="workspace-copy"><strong>Universal Growth</strong><span>Personal workspace</span></div>
          <ChevronDown size={15} className="workspace-chevron" />
        </div>

        <div className="nav-section-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ label, icon: Icon }) => (
            <button
              className={`nav-link ${page === label ? "active" : ""}`}
              key={label}
              onClick={() => setPage(label)}
              aria-label={label}
              aria-current={page === label ? "page" : undefined}
            >
              <Icon size={17} strokeWidth={1.8} />
              <span>{label}</span>
              {label === "Projects" && projects.length > 0 && (
                <span className="nav-count">{projects.length}</span>
              )}
              {label === "Agent Activity" && <span className="nav-count">0</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-divider" />
          <button className={`nav-link ${page === "Settings" ? "active" : ""}`} onClick={() => setPage("Settings")} aria-label="Settings">
            <Settings size={17} strokeWidth={1.8} /><span>Settings</span>
          </button>
          <a className="help-card" href={`${getApiBaseUrl()}/docs`} target="_blank" rel="noreferrer">
            <div className="help-icon"><CircleHelp size={16} /></div>
            <div><strong>API reference</strong><span>Open interactive docs</span></div>
            <ExternalLink size={13} className="help-external" />
          </a>
          <div className="profile-row">
            <div className="profile-avatar">UG</div>
            <div className="profile-copy"><strong>Universal Growth</strong><span>Local workspace</span></div>
            <ChevronDown size={15} className="profile-menu-icon" aria-hidden="true" />
          </div>
        </div>
      </aside>

      <main className="main-column min-w-0 flex-1">
        <header className="topbar flex items-center justify-between">
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{title}</strong></div>
          <div className="topbar-actions">
            <div className={`connection-pill ${connection.state === "offline" ? "is-offline" : connection.state === "loading" ? "is-loading" : connection.health.status === "healthy" ? "is-healthy" : "is-degraded"}`}>
              {connection.state === "loading" ? <LoaderCircle size={14} className="spin" /> : connection.state === "offline" ? <WifiOff size={14} /> : <span className="status-dot" />}
              <span>{connection.state === "loading" ? "Checking system" : connection.state === "offline" ? "API unavailable" : connection.health.status === "healthy" ? "All systems operational" : "System needs attention"}</span>
            </div>
            <button className="icon-button refresh-button" onClick={() => void refresh()} disabled={refreshing} aria-label="Refresh system status" title="Refresh system status">
              <RefreshCw size={15} className={refreshing ? "spin" : ""} />
            </button>
            <span className="top-avatar" aria-hidden="true">UG</span>
          </div>
        </header>

        <div className="page-content">
          {errorBanner && (
            <div className="workspace-alert" role="alert">
              <div className="flex items-center gap-2">
                <AlertCircle size={16} />
                <span>{errorBanner}</span>
              </div>
              <button className="icon-button" onClick={() => setErrorBanner(null)} aria-label="Dismiss error">
                <X size={14} />
              </button>
            </div>
          )}

          {page === "Overview" && (
            <Overview
              connection={connection}
              projects={projects}
              onOpenSettings={() => setPage("Settings")}
              onOpenProjects={() => setPage("Projects")}
              onNewProject={() => { setPage("Projects"); setModalOpen(true); }}
            />
          )}
          {page === "Projects" && (
            <ProjectsPage
              projects={projects}
              loading={loadingProjects}
              modalOpen={modalOpen}
              onOpenModal={() => setModalOpen(true)}
              onCloseModal={() => setModalOpen(false)}
              onProjectCreated={(p) => { setProjects((prev) => [p, ...prev]); setModalOpen(false); }}
              onProjectUpdated={handleProjectUpdated}
              onProjectDeleted={(id) => setProjects((prev) => prev.filter((p) => p.id !== id))}
              onError={(msg) => setErrorBanner(msg)}
            />
          )}
          {page === "Agent Activity" && <EmptyPage kind="activity" />}
          {page === "Settings" && <SettingsPage connection={connection} />}
        </div>
      </main>
    </div>
  );
}

// ─── Overview ────────────────────────────────────────────────────────────────

function Overview({
  connection,
  projects,
  onOpenSettings,
  onOpenProjects,
  onNewProject,
}: {
  connection: Connection;
  projects: Project[];
  onOpenSettings: () => void;
  onOpenProjects: () => void;
  onNewProject: () => void;
}) {
  const health = connection.state === "online" ? connection.health : undefined;
  const connectedCount = health
    ? [health.database, health.redis].filter((item) => item.status === "connected").length
    : undefined;

  return (
    <>
      <div className="page-heading flex items-end justify-between">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> YOUR WORKSPACE</div>
          <h1>Good to see you<span className="heading-period">.</span></h1>
          <p className="page-subtitle">A clear view of your growth systems, all in one place.</p>
        </div>
        <button className="button button-secondary" onClick={onOpenSettings}><Settings size={15} /> Configure system</button>
      </div>

      <section className="metrics-grid" aria-label="System summary">
        <MetricCard
          icon={Radio}
          label="APPLICATION API"
          value={connection.state === "loading" ? "Checking" : connection.state === "offline" ? "Offline" : "Reachable"}
          detail={connection.state === "online" ? `Version ${connection.system?.version ?? "—"}` : connection.state === "offline" ? "Could not reach the backend" : "Checking backend connection"}
          tone={connection.state === "online" ? "lime" : connection.state === "offline" ? "rose" : "neutral"}
          trend={connection.state === "online" ? <ArrowUpRight size={14} /> : connection.state === "offline" ? <ArrowDownRight size={14} /> : <LoaderCircle size={14} className="spin" />}
        />
        <MetricCard
          icon={Database}
          label="INFRASTRUCTURE"
          value={connectedCount === undefined ? "—" : `${connectedCount} / 2`}
          detail={health ? "Database and Redis connections" : "Waiting for backend health data"}
          tone={connectedCount === 2 ? "lime" : health ? "amber" : "neutral"}
          trend={health ? <ShieldCheck size={14} /> : <LoaderCircle size={14} className="spin" />}
        />
        <MetricCard
          icon={Command}
          label="PROJECTS"
          value={String(projects.length)}
          detail={projects.length === 0 ? "No projects yet — add your first" : projects.length === 1 ? "1 active project" : `${projects.length} projects in workspace`}
          tone="violet"
          trend={<Plus size={14} />}
        />
      </section>

      <div className="overview-grid">
        <section className="panel readiness-panel">
          <div className="panel-heading">
            <div><span className="panel-kicker">LIVE STATUS</span><h2>System health</h2></div>
            <span className="live-label"><span /> LIVE</span>
          </div>
          {health ? (
            <div className="health-list">
              <HealthRow icon={Server} label="Backend API" detail="Application process" status={{ status: "connected", message: "Reachable" }} />
              <HealthRow icon={Database} label="PostgreSQL" detail={health.database.message} status={health.database} />
              <HealthRow icon={Radio} label="Redis" detail={health.redis.message} status={health.redis} />
            </div>
          ) : (
            <div className="status-message">
              {connection.state === "loading" ? <LoaderCircle className="spin" size={17} /> : <WifiOff size={17} />}
              <div><strong>{connection.state === "loading" ? "Checking your backend" : "Backend could not be reached"}</strong><span>{connection.state === "offline" ? `Confirm the API is running at ${getApiBaseUrl()}.` : "Live component status will appear here."}</span></div>
            </div>
          )}
          <div className="panel-footer">
            <span>{connection.state === "online" ? `Last checked ${connection.checkedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Health checks run automatically"}</span>
            <button className="text-button" onClick={onOpenSettings}>View configuration <ArrowUpRight size={13} /></button>
          </div>
        </section>

        <section className="panel workspace-panel">
          <div className="panel-heading">
            <div><span className="panel-kicker">YOUR WORKSPACE</span><h2>Growth projects</h2></div>
            <button className="icon-button" onClick={onNewProject} aria-label="Add new project"><Plus size={16} /></button>
          </div>
          {projects.length === 0 ? (
            <div className="project-empty-compact">
              <div className="empty-art"><div className="empty-art-center"><Sparkles size={20} /></div><span className="orbit orbit-one" /><span className="orbit orbit-two" /><span className="orbit-dot" /></div>
              <strong>No projects yet</strong>
              <span>Projects will show up here when added.</span>
            </div>
          ) : (
            <div className="compact-project-list">
              {projects.slice(0, 4).map((p) => (
                <div key={p.id} className="compact-project-row" onClick={onOpenProjects} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onOpenProjects()}>
                  <div className="compact-project-name">{p.name}</div>
                  <span className={`badge badge-${p.status}`}>{p.status}</span>
                </div>
              ))}
              {projects.length > 4 && (
                <button className="text-button" onClick={onOpenProjects}>+{projects.length - 4} more</button>
              )}
            </div>
          )}
          <button className="panel-link" onClick={onOpenProjects}>Explore projects <ArrowUpRight size={14} /></button>
        </section>
      </div>

      <section className="panel foundation-panel">
        <div className="foundation-icon"><Sparkles size={18} /></div>
        <div className="foundation-copy"><span className="panel-kicker">PROJECT FOUNDATION</span><h2>Your growth workspace is taking shape.</h2><p>The core application, dashboard, and local infrastructure are ready to configure. Connect services to see their live status here.</p></div>
        <button className="button button-quiet" onClick={onOpenSettings}>Review setup <ArrowUpRight size={14} /></button>
        <div className="foundation-glow" />
      </section>
    </>
  );
}

// ─── Projects page ────────────────────────────────────────────────────────────

const CATEGORY_OPTIONS: { value: ProjectCategory; label: string }[] = [
  { value: "mobile_app", label: "Mobile app" },
  { value: "web_app", label: "Web app" },
  { value: "saas", label: "SaaS" },
  { value: "ecommerce", label: "E-commerce" },
  { value: "other", label: "Other" },
];

function ProjectsPage({
  projects,
  loading,
  modalOpen,
  onOpenModal,
  onCloseModal,
  onProjectCreated,
  onProjectUpdated,
  onProjectDeleted,
  onError,
}: {
  projects: Project[];
  loading: boolean;
  modalOpen: boolean;
  onOpenModal: () => void;
  onCloseModal: () => void;
  onProjectCreated: (p: Project) => void;
  onProjectUpdated: (p: Project) => void;
  onProjectDeleted: (id: string) => void;
  onError: (msg: string) => void;
}) {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);

  const handleDelete = async (p: Project) => {
    if (!window.confirm(`Delete "${p.name}"? This cannot be undone.`)) return;
    try {
      await deleteProject(p.id);
      onProjectDeleted(p.id);
      if (selectedProject?.id === p.id) {
        setSelectedProject(null);
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to delete project.");
    }
  };

  const filteredProjects = projects.filter((p) => {
    if (statusFilter !== "all" && p.status !== statusFilter) return false;
    if (categoryFilter !== "all" && p.category !== categoryFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = p.name.toLowerCase().includes(q);
      const matchSlug = p.slug.toLowerCase().includes(q);
      const matchDesc = p.description?.toLowerCase().includes(q) ?? false;
      if (!matchName && !matchSlug && !matchDesc) return false;
    }
    return true;
  });

  return (
    <div className="empty-page-wrap">
      <div className="page-heading flex items-end justify-between">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> WORKSPACE</div>
          <h1>Projects<span className="heading-period">.</span></h1>
          <p className="page-subtitle">Organize the products you want to grow.</p>
        </div>
        <button className="button button-primary" onClick={onOpenModal}><Plus size={15} /> New project</button>
      </div>

      {projects.length > 0 && (
        <div className="workspace-filter-bar">
          <div className="filter-left-group">
            <div className="search-input-wrap">
              <Search size={14} />
              <input
                type="text"
                className="search-input"
                placeholder="Search projects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search projects"
              />
            </div>

            <div className="filter-pills" role="tablist" aria-label="Status filter">
              {["all", "active", "paused", "archived"].map((st) => (
                <button
                  key={st}
                  className={`filter-pill ${statusFilter === st ? "active" : ""}`}
                  onClick={() => setStatusFilter(st)}
                  type="button"
                >
                  {st.charAt(0).toUpperCase() + st.slice(1)}
                </button>
              ))}
            </div>

            <select
              className="category-select"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              aria-label="Category filter"
            >
              <option value="all">All categories</option>
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {loading ? (
        <div className="workspace-loading">
          <LoaderCircle size={24} className="spin text-blue-500" />
          <span>Loading workspace projects...</span>
        </div>
      ) : projects.length === 0 ? (
        <section className="empty-page panel">
          <div className="empty-page-icon"><Command size={22} strokeWidth={1.6} /></div>
          <span className="panel-kicker">PROJECT WORKSPACE</span>
          <h2>Your projects start here</h2>
          <p>There are no projects in this workspace. Add a product when you're ready to start organizing growth work.</p>
          <button className="button button-primary" style={{ marginTop: "1.25rem" }} onClick={onOpenModal}><Plus size={15} /> Add your first project</button>
        </section>
      ) : filteredProjects.length === 0 ? (
        <section className="empty-page panel" style={{ padding: "3rem 1rem" }}>
          <div className="empty-page-icon"><Search size={22} strokeWidth={1.6} /></div>
          <h2>No matching projects</h2>
          <p>No projects match your current filters or search term.</p>
          <button
            className="button button-secondary"
            style={{ marginTop: "1rem" }}
            onClick={() => { setStatusFilter("all"); setCategoryFilter("all"); setSearchQuery(""); }}
          >
            Clear filters
          </button>
        </section>
      ) : (
        <div className="projects-grid">
          {filteredProjects.map((p) => (
            <ProjectCard
              key={p.id}
              project={p}
              onSelect={() => setSelectedProject(p)}
              onEdit={() => setEditingProject(p)}
              onDelete={() => void handleDelete(p)}
            />
          ))}
        </div>
      )}

      {modalOpen && (
        <CreateProjectModal onClose={onCloseModal} onCreated={onProjectCreated} />
      )}

      {selectedProject && (
        <ProjectDetailModal
          project={selectedProject}
          onClose={() => setSelectedProject(null)}
          onEdit={() => {
            setEditingProject(selectedProject);
            setSelectedProject(null);
          }}
          onDelete={() => void handleDelete(selectedProject)}
        />
      )}

      {editingProject && (
        <EditProjectModal
          project={editingProject}
          onClose={() => setEditingProject(null)}
          onUpdated={(updated) => {
            onProjectUpdated(updated);
            setEditingProject(null);
          }}
        />
      )}
    </div>
  );
}

function ProjectCard({
  project,
  onSelect,
  onEdit,
  onDelete,
}: {
  project: Project;
  onSelect: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <article
      className="project-card panel"
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      <div className="project-card-header">
        <div>
          <div className="project-card-name">{project.name}</div>
          <div className="project-card-slug">/{project.slug}</div>
        </div>
        <div className="project-card-actions">
          <button
            className="icon-button"
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
            aria-label={`Edit ${project.name}`}
            title="Edit project"
          >
            <Pencil size={14} />
          </button>
          <button
            className="icon-button danger"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            aria-label={`Delete ${project.name}`}
            title="Delete project"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      {project.description && <p className="project-card-desc">{project.description}</p>}
      <div className="project-card-footer">
        <span className="badge badge-category">{project.category.replace("_", " ")}</span>
        <span className={`badge badge-${project.status}`}>{project.status}</span>
      </div>
    </article>
  );
}

// ─── Project detail modal ─────────────────────────────────────────────────────

function ProjectDetailModal({
  project,
  onClose,
  onEdit,
  onDelete,
}: {
  project: Project;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Project details" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-dialog large">
        <div className="modal-header">
          <div>
            <h2>{project.name}</h2>
            <div className="detail-header-tags">
              <span className="project-card-slug">/{project.slug}</span>
              <span className={`badge badge-${project.status}`}>{project.status}</span>
              <span className="badge badge-category">{project.category.replace("_", " ")}</span>
            </div>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close modal"><X size={18} /></button>
        </div>

        <div className="detail-section">
          <div className="detail-section-title">Overview</div>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="label">Project ID</span>
              <span className="value font-mono text-xs text-slate-400">{project.id}</span>
            </div>
            <div className="detail-item">
              <span className="label">Owner / Workspace</span>
              <span className="value flex items-center gap-1.5"><User size={13} className="text-slate-400" />{project.owner ?? "default"}</span>
            </div>
            <div className="detail-item">
              <span className="label">Created</span>
              <span className="value flex items-center gap-1.5"><Calendar size={13} className="text-slate-400" />{new Date(project.created_at).toLocaleDateString()}</span>
            </div>
            <div className="detail-item">
              <span className="label">Last updated</span>
              <span className="value flex items-center gap-1.5"><Calendar size={13} className="text-slate-400" />{new Date(project.updated_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>

        <div className="detail-section">
          <div className="detail-section-title">Description</div>
          <div className="detail-desc-box">
            {project.description || <span className="italic text-slate-500">No description provided for this product.</span>}
          </div>
        </div>

        <div className="detail-section">
          <div className="detail-section-title">Target Audience</div>
          <div className="detail-desc-box">
            {project.target_audience || <span className="italic text-slate-500">No target audience specified.</span>}
          </div>
        </div>

        {project.metadata && Object.keys(project.metadata).length > 0 && (
          <div className="detail-section">
            <div className="detail-section-title">Product Metadata</div>
            <pre className="metadata-box">{JSON.stringify(project.metadata, null, 2)}</pre>
          </div>
        )}

        <div className="modal-actions" style={{ marginTop: "24px" }}>
          <button type="button" className="button button-danger" onClick={onDelete}>
            <Trash2 size={14} /> Delete product
          </button>
          <div className="flex items-center gap-2">
            <button type="button" className="button button-secondary" onClick={onClose}>Close</button>
            <button type="button" className="button button-primary" onClick={onEdit}>
              <Pencil size={14} /> Edit product
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Edit project modal ───────────────────────────────────────────────────────

function EditProjectModal({
  project,
  onClose,
  onUpdated,
}: {
  project: Project;
  onClose: () => void;
  onUpdated: (p: Project) => void;
}) {
  const [name, setName] = useState(project.name);
  const [category, setCategory] = useState<ProjectCategory>(project.category);
  const [status, setStatus] = useState<ProjectStatus>(project.status);
  const [description, setDescription] = useState(project.description ?? "");
  const [targetAudience, setTargetAudience] = useState(project.target_audience ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Project name is required.");
      return;
    }
    setSubmitting(true);
    try {
      const payload: ProjectUpdateInput = {
        name: name.trim(),
        category,
        status,
        description: description.trim() || undefined,
        target_audience: targetAudience.trim() || undefined,
      };
      const updated = await updateProject(project.id, payload);
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update project.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Edit project" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-dialog">
        <div className="modal-header">
          <h2>Edit project</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close modal"><X size={18} /></button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="modal-form">
          <div className="form-field">
            <label className="form-label" htmlFor="edit-name">Project name *</label>
            <input
              id="edit-name"
              className="form-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="form-field">
              <label className="form-label" htmlFor="edit-category">Category</label>
              <select
                id="edit-category"
                className="form-select"
                value={category}
                onChange={(e) => setCategory(e.target.value as ProjectCategory)}
              >
                {CATEGORY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="edit-status">Status</label>
              <select
                id="edit-status"
                className="form-select"
                value={status}
                onChange={(e) => setStatus(e.target.value as ProjectStatus)}
              >
                <option value="active">Active</option>
                <option value="paused">Paused</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="edit-desc">Description</label>
            <textarea
              id="edit-desc"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="edit-audience">Target audience</label>
            <textarea
              id="edit-audience"
              className="form-textarea"
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              rows={2}
            />
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="modal-actions">
            <button type="button" className="button button-secondary" onClick={onClose} disabled={submitting}>Cancel</button>
            <button type="submit" className="button button-primary" disabled={submitting}>
              {submitting ? <><LoaderCircle size={14} className="spin" /> Saving…</> : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Create project modal ─────────────────────────────────────────────────────

function CreateProjectModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (p: Project) => void;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState<ProjectCategory>("mobile_app");
  const [description, setDescription] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  const quickFill = () => {
    setName("Android Part-Time Jobs App");
    setCategory("mobile_app");
    setDescription("A mobile application for finding and applying to part-time job listings on Android devices.");
    setTargetAudience("Job seekers aged 18–35 looking for flexible part-time work via Android smartphones.");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) { setError("Project name is required."); return; }
    setSubmitting(true);
    try {
      const payload: ProjectCreateInput = {
        name: name.trim(),
        category,
        description: description.trim() || undefined,
        target_audience: targetAudience.trim() || undefined,
      };
      const created = await createProject(payload);
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Create project" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-dialog">
        <div className="modal-header">
          <h2>New project</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close modal"><X size={18} /></button>
        </div>

        <button type="button" className="button button-quiet quick-fill-btn" onClick={quickFill}>
          Quick-fill sample data
        </button>

        <form onSubmit={(e) => void handleSubmit(e)} className="modal-form">
          <div className="form-field">
            <label className="form-label" htmlFor="proj-name">Project name *</label>
            <input
              ref={nameRef}
              id="proj-name"
              className="form-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Android Part-Time Jobs App"
              required
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="proj-category">Category</label>
            <select
              id="proj-category"
              className="form-select"
              value={category}
              onChange={(e) => setCategory(e.target.value as ProjectCategory)}
            >
              {CATEGORY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="proj-desc">Description</label>
            <textarea
              id="proj-desc"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this project about?"
              rows={3}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="proj-audience">Target audience</label>
            <textarea
              id="proj-audience"
              className="form-textarea"
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              placeholder="Who are you building this for?"
              rows={2}
            />
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="modal-actions">
            <button type="button" className="button button-secondary" onClick={onClose} disabled={submitting}>Cancel</button>
            <button type="submit" className="button button-primary" disabled={submitting}>
              {submitting ? <><LoaderCircle size={14} className="spin" /> Creating…</> : "Create project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Shared components ────────────────────────────────────────────────────────

function MetricCard({ icon: Icon, label, value, detail, tone, trend }: { icon: LucideIcon; label: string; value: string; detail: string; tone: string; trend: ReactNode }) {
  return (
    <section className="metric-card panel">
      <div className="metric-top"><span className={`metric-icon ${tone}`}><Icon size={16} strokeWidth={1.9} /></span><span className={`metric-trend ${tone}`}>{trend}</span></div>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </section>
  );
}

function HealthRow({ icon: Icon, label, detail, status }: { icon: LucideIcon; label: string; detail: string; status: ComponentHealth }) {
  const labelByStatus = { connected: "Connected", not_configured: "Not configured", unavailable: "Unavailable" };
  return (
    <div className="health-row">
      <div className="health-row-icon"><Icon size={16} strokeWidth={1.8} /></div>
      <div className="health-row-copy"><strong>{label}</strong><span>{detail}</span></div>
      <StatusBadge status={status.status} label={labelByStatus[status.status]} />
    </div>
  );
}

function StatusBadge({ status, label }: { status: ComponentHealth["status"]; label: string }) {
  return <span className={`status-badge ${status}`}><span className="status-dot" />{label}</span>;
}

function EmptyPage(_: { kind: "activity" }) {
  return (
    <div className="empty-page-wrap">
      <div className="page-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> WORKSPACE</div><h1>Agent activity<span className="heading-period">.</span></h1><p className="page-subtitle">A timeline of actions and outcomes across your workspace.</p></div>
      </div>
      <section className="empty-page panel">
        <div className="empty-page-icon"><Activity size={22} strokeWidth={1.6} /></div>
        <span className="panel-kicker">ACTIVITY TIMELINE</span>
        <h2>Nothing happening yet</h2>
        <p>Agent activity and campaign events will appear here as work is introduced to the platform.</p>
      </section>
    </div>
  );
}

function SettingsPage({ connection }: { connection: Connection }) {
  const health = connection.state === "online" ? connection.health : undefined;
  const system = connection.state === "online" ? connection.system : undefined;
  return (
    <div className="settings-page">
      <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> PREFERENCES</div><h1>Settings<span className="heading-period">.</span></h1><p className="page-subtitle">Review this dashboard's connection and runtime configuration.</p></div></div>
      <section className="panel settings-section">
        <div className="settings-section-heading"><div className="settings-section-icon"><Server size={16} /></div><div><h2>Application</h2><p>Values reported by the running backend.</p></div></div>
        <div className="settings-rows">
          <SettingRow label="Application name" value={system?.name ?? (connection.state === "loading" ? "Loading…" : "Unavailable")} />
          <SettingRow label="Version" value={system?.version ?? "—"} />
          <SettingRow label="Environment" value={system?.environment ?? "—"} />
          <SettingRow label="API endpoint" value={getApiBaseUrl()} mono />
        </div>
      </section>
      <section className="panel settings-section">
        <div className="settings-section-heading"><div className="settings-section-icon"><Database size={16} /></div><div><h2>Infrastructure</h2><p>Connection states come from the backend health endpoint.</p></div></div>
        <div className="settings-rows">
          <SettingRow label="PostgreSQL" value={health?.database.message ?? "Waiting for health check"} status={health?.database} />
          <SettingRow label="Redis" value={health?.redis.message ?? "Waiting for health check"} status={health?.redis} />
        </div>
      </section>
      <div className="settings-note"><ShieldCheck size={16} /><span>Configuration is managed through environment variables. See the Windows setup guide in the project README.</span></div>
    </div>
  );
}

function SettingRow({ label, value, mono, status }: { label: string; value: string; mono?: boolean; status?: ComponentHealth }) {
  return <div className="setting-row"><span>{label}</span><div className="setting-value">{status ? <StatusBadge status={status.status} label={status.status.replace("_", " ")} /> : <strong className={mono ? "mono" : ""}>{value}</strong>}</div></div>;
}

export default App;
