const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type IntegrationHealth = {
  key: string;
  display_name: string;
  connected: boolean;
  last_sync_at: string | null;
  last_error: string | null;
  records_synced: number;
};

export type HealthResponse = {
  status: "ok" | "degraded";
  integrations: IntegrationHealth[];
  ai_enabled: boolean;
};

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}
