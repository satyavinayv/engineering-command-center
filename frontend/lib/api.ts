const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
// Server-side only (no NEXT_PUBLIC_ prefix) - fetches in page.tsx run on
// the server, so this never reaches the browser bundle.
const API_KEY = process.env.API_KEY || "";

export type IntegrationHealth = {
  key: string;
  display_name: string;
  configured: boolean;
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

export type JiraIssue = {
  key: string;
  summary: string;
  status: string;
  priority: string;
  issue_type: string;
  assignee: string | null;
  reporter: string | null;
  labels: string[];
  url: string;
  updated_at: string | null;
};

export type GitLabMergeRequest = {
  source_id: number;
  iid: number;
  title: string;
  author: string;
  computed_state: string;
  pipeline_status: string | null;
  reviewers: string[];
  web_url: string;
  updated_at: string | null;
};

export type TestExecution = {
  test_case_key: string;
  jira_summary: string | null;
  jira_url: string | null;
  status: string | null;
  environment: string;
  executed_at: string | null;
  opensearch_url: string | null;
};

async function authedFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    headers: API_KEY ? { "X-API-Key": API_KEY } : {},
  });
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status}`);
  }
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}

export async function getJiraIssues(): Promise<JiraIssue[]> {
  return authedFetch<JiraIssue[]>("/api/jira/issues");
}

export async function getMyOpenMergeRequests(): Promise<GitLabMergeRequest[]> {
  return authedFetch<GitLabMergeRequest[]>("/api/gitlab/merge-requests/mine");
}

export async function getMergeRequestsToReview(): Promise<GitLabMergeRequest[]> {
  return authedFetch<GitLabMergeRequest[]>("/api/gitlab/merge-requests/to-review");
}

export async function getTestExecutions(): Promise<TestExecution[]> {
  return authedFetch<TestExecution[]>("/api/tests/executions");
}
