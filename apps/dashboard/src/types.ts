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
