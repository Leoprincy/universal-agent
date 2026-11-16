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
}

export interface ProjectCreateInput {
  name: string;
  slug?: string;
  description?: string;
  category: ProjectCategory;
  target_audience?: string;
  metadata?: Record<string, unknown>;
}
