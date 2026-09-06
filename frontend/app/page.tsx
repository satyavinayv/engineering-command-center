import {
  getHealth,
  getJiraIssues,
  getMergeRequestsToReview,
  getMyOpenMergeRequests,
  getTestExecutions,
  type GitLabMergeRequest,
  type HealthResponse,
  type JiraIssue,
  type TestExecution,
} from "@/lib/api";

function formatTime(iso: string | null): string {
  if (!iso) return "never";
  return new Date(iso).toLocaleString();
}

const MR_STATE_LABELS: Record<string, string> = {
  MERGED: "🟢 Merged",
  APPROVED: "🟢 Approved",
  CLOSED: "⚪ Closed",
  DRAFT: "⚪ Draft",
  PIPELINE_FAILED: "🔴 Pipeline Failed",
  REVIEWER_ACTION_REQUIRED: "🔴 Reviewer Action Required",
  WAITING_FOR_PIPELINE: "🔵 Waiting for Pipeline",
  WAITING_FOR_REVIEWER: "🟡 Waiting for Reviewer",
  OPEN: "⚪ Open",
};

const STATUS_LABELS: Record<string, string> = {
  PASS: "🟢 PASS",
  PASSED: "🟢 PASS",
  FAIL: "🔴 FAIL",
  FAILED: "🔴 FAIL",
  RUNNING: "🟡 RUNNING",
  SKIP: "⚪ SKIPPED",
  SKIPPED: "⚪ SKIPPED",
};

async function safeLoad<T>(loader: () => Promise<T>, fallback: T): Promise<{ data: T; error: string | null }> {
  try {
    return { data: await loader(), error: null };
  } catch (err) {
    return { data: fallback, error: err instanceof Error ? err.message : "Unknown error" };
  }
}

export default async function Home() {
  let health: HealthResponse | null = null;
  let fetchError: string | null = null;

  try {
    health = await getHealth();
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Unknown error";
  }

  // Each of these degrades independently - one failing (e.g. Jira not
  // configured yet) never blocks the others from rendering (spec
  // section 28).
  const [jiraResult, myMrsResult, toReviewResult, testExecResult] = await Promise.all([
    safeLoad<JiraIssue[]>(getJiraIssues, []),
    safeLoad<GitLabMergeRequest[]>(getMyOpenMergeRequests, []),
    safeLoad<GitLabMergeRequest[]>(getMergeRequestsToReview, []),
    safeLoad<TestExecution[]>(getTestExecutions, []),
  ]);

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
        <h2>My Open Merge Requests</h2>
        {myMrsResult.error && <p className="muted">Couldn&apos;t load: {myMrsResult.error}</p>}
        {!myMrsResult.error && myMrsResult.data.length === 0 && (
          <p className="muted">None open, or GitLab isn&apos;t configured yet.</p>
        )}
        {myMrsResult.data.map((mr) => (
          <div className="integration-row" key={mr.source_id}>
            <a href={mr.web_url} target="_blank" rel="noreferrer" style={{ color: "inherit" }}>
              {mr.title}
            </a>
            <span className="muted">{MR_STATE_LABELS[mr.computed_state] ?? mr.computed_state}</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Merge Requests To Review</h2>
        {toReviewResult.error && <p className="muted">Couldn&apos;t load: {toReviewResult.error}</p>}
        {!toReviewResult.error && toReviewResult.data.length === 0 && (
          <p className="muted">Nothing assigned to you right now, or GitLab isn&apos;t configured yet.</p>
        )}
        {toReviewResult.data.map((mr) => (
          <div className="integration-row" key={mr.source_id}>
            <a href={mr.web_url} target="_blank" rel="noreferrer" style={{ color: "inherit" }}>
              {mr.title}
            </a>
            <span className="muted">by {mr.author}</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>My Jira Work</h2>
        {jiraResult.error && <p className="muted">Couldn&apos;t load: {jiraResult.error}</p>}
        {!jiraResult.error && jiraResult.data.length === 0 && (
          <p className="muted">No synced issues yet, or Jira isn&apos;t configured yet.</p>
        )}
        {jiraResult.data.map((issue) => (
          <div className="integration-row" key={issue.key}>
            <a href={issue.url} target="_blank" rel="noreferrer" style={{ color: "inherit" }}>
              {issue.key} · {issue.summary}
            </a>
            <span className="muted">{issue.status}</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Automation Test Status</h2>
        {testExecResult.error && <p className="muted">Couldn&apos;t load: {testExecResult.error}</p>}
        {!testExecResult.error && testExecResult.data.length === 0 && (
          <p className="muted">
            No executions synced yet, or OpenSearch isn&apos;t configured yet.
          </p>
        )}
        {testExecResult.data.map((exec) => (
          <div className="integration-row" key={exec.test_case_key}>
            <span>
              {exec.jira_url ? (
                <a href={exec.jira_url} target="_blank" rel="noreferrer" style={{ color: "inherit" }}>
                  {exec.test_case_key}
                </a>
              ) : (
                exec.test_case_key
              )}
              {exec.jira_summary ? ` · ${exec.jira_summary}` : ""}
            </span>
            <span className="muted">
              {exec.status
                ? STATUS_LABELS[exec.status.toUpperCase()] ?? exec.status
                : "⚪ status field not mapped yet"}{" "}
              · {formatTime(exec.executed_at)}
            </span>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>What&apos;s next</h2>
        <p className="muted">
          Calendar, Gmail, the unified Action Required feed, and AI
          summaries land in the phases described in{" "}
          <code>docs/PHASES.md</code>.
        </p>
      </div>
    </main>
  );
}
