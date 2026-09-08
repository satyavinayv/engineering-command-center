import { StatusDot } from "./Badges";
import type { IntegrationHealth } from "@/lib/api";

function formatTime(iso: string | null): string {
if (!iso) return "never";

return new Date(iso).toLocaleString();
}

export function SystemHealth({
integrations,
aiEnabled,
error,
}: {
integrations: IntegrationHealth[] | null;
aiEnabled: boolean;
error: string | null;
}) {
return (
<section className="card">
<h2>System Status</h2>

  {error && (
    <p className="error-text">
      Could not reach the backend ({error}).
      Is the backend running?
    </p>
  )}

  {!error && !integrations && (
    <p className="muted">Loading status...</p>
  )}

  {!error &&
    integrations &&
    integrations.length === 0 && (
      <p className="muted">
        No integrations registered yet.
      </p>
    )}

  {!error &&
    integrations &&
    integrations.length > 0 && (
      <div className="integration-grid">
        {integrations.map((integration) => (
          <div
            className="integration-row"
            key={integration.key}
          >
            <span>
              <StatusDot ok={integration.connected} />
              {integration.display_name}
            </span>

            <span className="muted">
              {integration.configured
                ? integration.connected
                  ? "Connected"
                  : "Disconnected"
                : "Not configured"}{" "}
              · last sync:{" "}
              {formatTime(integration.last_sync_at)}
            </span>
          </div>
        ))}

        <div className="integration-row">
          <span>AI Layer</span>

          <span className="muted">
            {aiEnabled ? "Enabled" : "Disabled"}
          </span>
        </div>
      </div>
    )}
</section>


);
}