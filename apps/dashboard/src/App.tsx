import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  ChevronDown,
  CircleHelp,
  Command,
  Database,
  ExternalLink,
  LayoutDashboard,
  LoaderCircle,
  Plus,
  Radio,
  RefreshCw,
  Server,
  Settings,
  ShieldCheck,
  Sparkles,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import { getApiBaseUrl, getHealth, getSystemInfo } from "./lib/api";
import type { ComponentHealth, HealthResponse, SystemInfo } from "./types";

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
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

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
          {page === "Overview" && <Overview connection={connection} onOpenSettings={() => setPage("Settings")} onOpenProjects={() => setPage("Projects")} />}
          {page === "Projects" && <EmptyPage kind="projects" />}
          {page === "Agent Activity" && <EmptyPage kind="activity" />}
          {page === "Settings" && <SettingsPage connection={connection} />}
        </div>
      </main>
    </div>
  );
}

function Overview({ connection, onOpenSettings, onOpenProjects }: { connection: Connection; onOpenSettings: () => void; onOpenProjects: () => void }) {
  const health = connection.state === "online" ? connection.health : undefined;
  const connectedCount = health ? [health.database, health.redis].filter((item) => item.status === "connected").length : undefined;

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
          icon={Server}
          label="ENVIRONMENT"
          value={connection.state === "online" ? (connection.system?.environment ?? "Available") : "—"}
          detail={connection.state === "online" ? "Active backend configuration" : "Unavailable until API responds"}
          tone="violet"
          trend={<Server size={14} />}
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
            <button className="icon-button" onClick={onOpenProjects} aria-label="Open projects"><Plus size={16} /></button>
          </div>
          <div className="project-empty-compact">
            <div className="empty-art"><div className="empty-art-center"><Sparkles size={20} /></div><span className="orbit orbit-one" /><span className="orbit orbit-two" /><span className="orbit-dot" /></div>
            <strong>No projects yet</strong>
            <span>Projects will show up here when added.</span>
          </div>
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

function EmptyPage({ kind }: { kind: "projects" | "activity" }) {
  const projects = kind === "projects";
  const Icon = projects ? Command : Activity;
  return (
    <div className="empty-page-wrap">
      <div className="page-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" /> WORKSPACE</div><h1>{projects ? "Projects" : "Agent activity"}<span className="heading-period">.</span></h1><p className="page-subtitle">{projects ? "Organize the products you want to grow." : "A timeline of actions and outcomes across your workspace."}</p></div>
      </div>
      <section className="empty-page panel">
        <div className="empty-page-icon"><Icon size={22} strokeWidth={1.6} /></div>
        <span className="panel-kicker">{projects ? "PROJECT WORKSPACE" : "ACTIVITY TIMELINE"}</span>
        <h2>{projects ? "Your projects start here" : "Nothing happening yet"}</h2>
        <p>{projects ? "There are no projects in this workspace. Add a product when you’re ready to start organizing growth work." : "Agent activity and campaign events will appear here as work is introduced to the platform."}</p>
      </section>
    </div>
  );
}

function SettingsPage({ connection }: { connection: Connection }) {
  const health = connection.state === "online" ? connection.health : undefined;
  const system = connection.state === "online" ? connection.system : undefined;
  return (
    <div className="settings-page">
      <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> PREFERENCES</div><h1>Settings<span className="heading-period">.</span></h1><p className="page-subtitle">Review this dashboard’s connection and runtime configuration.</p></div></div>
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
