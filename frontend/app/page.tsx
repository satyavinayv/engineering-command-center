import { getHealth, type HealthResponse } from "@/lib/api";

function formatTime(iso: string | null): string {
  if (!iso) return "never";
  return new Date(iso).toLocaleString();
}

export default async function Home() {
  let health: HealthResponse | null = null;
  let fetchError: string | null = null;

  try {
    health = await getHealth();
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Unknown error";
  }

  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  return (
    <main className="page">
      <div className="header">
        <h1>Engineering Command Center</h1>
        <span className="date">{today}</span>
      </div>

      {fetchError && (
        <div className="error-banner">
          Could not reach the backend at the configured API URL ({fetchError}).
          Is <code>uvicorn app.main:app --reload</code> running? The dashboard
          should never go fully blank just because one thing is down — this
          message is Phase 1's version of that principle.
        </div>
      )}

      <div className="card">
        <h2>System Health</h2>
        {health ? (
          <>
            {health.integrations.map((integration) => (
              <div className="integration-row" key={integration.key}>
                <span>
                  <span
                    className={`dot ${integration.connected ? "connected" : "disconnected"}`}
                  />
                  {integration.display_name}
                </span>
                <span className="muted">
                  {integration.connected ? "Connected" : "Disconnected"} · last sync:{" "}
                  {formatTime(integration.last_sync_at)}
                </span>
              </div>
            ))}
            <div className="integration-row" style={{ marginTop: 8 }}>
              <span>AI Layer</span>
              <span className="muted">
                {health.ai_enabled ? "Enabled" : "Disabled / Optional (Phase 7)"}
              </span>
            </div>
          </>
        ) : (
          <p className="muted">No health data available.</p>
        )}
      </div>

      <div className="card">
        <h2>What&apos;s next</h2>
        <p className="muted">
          This is the Phase 1 foundation shell — real Action Required,
          GitLab, Jira, Calendar, and Automation sections land in the
          phases described in <code>docs/PHASES.md</code>.
        </p>
      </div>
    </main>
  );
}
