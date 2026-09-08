const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// Server-side only.
// API_KEY is intentionally NOT prefixed with NEXT_PUBLIC_.
const API_KEY = process.env.API_KEY || "";

export class BackendUnavailableError extends Error {
}

async function authedFetch<T>(
    path: string,
    init?: RequestInit
): Promise<T> {
    let res: Response;

    try {
        res = await fetch(`${API_BASE_URL}${path}`, {
            cache: "no-store",
            ...init,
            headers: {
                ...(API_KEY ? {"X-API-Key": API_KEY} : {}),
                ...(init?.headers || {}),
            },
        });
    } catch (err) {
        throw new BackendUnavailableError(
            err instanceof Error
                ? err.message
                : "Could not reach the backend"
        );
    }

    if (!res.ok) {
        throw new Error(`${path} failed: ${res.status}`);
    }

    return res.json();
}

// ---------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------

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

export type ActionItem = {
    source: "gitlab" | "jira" | "calendar" | "gmail" | "tests";
    priority: "P0" | "P1" | "P2" | "P3";
    title: string;
    description: string;
    url: string | null;
    timestamp: string | null;
    key: string;
};

export type NextCalendarEvent = {
    source_uid: string;
    title: string;
    start_at: string | null;
    calendar_link: string | null;
    my_rsvp_status: string;
};

export type DashboardSummary = {
    generated_at: string;

    health: {
        status: "ok" | "degraded";
    };

    action_required: {
        count: number;
        top_items: ActionItem[];
    };

    calendar: {
        next_event: NextCalendarEvent | null;
        pending_rsvp_count: number;
    };

    gmail: {
        action_required_count: number;
        unread_count: number;
    };

    jira: {
        active_count: number;
        important_count: number;
    };

    gitlab: {
        review_waiting_count: number;
        failed_pipeline_count: number;
    };

    tests: {
        fail_count: number;
        pass_count: number;
    };

    ai: {
        enabled: boolean;
        available: boolean;
        cached: boolean;
        generated_at: string | null;
    };
};

export type DailyBriefing = {
    available: boolean;
    content: string | null;
    generated_by: string | null;
    created_at: string | null;
    cached: boolean;
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

export type CalendarEvent = {
    source_uid: string;
    title: string;
    start_at: string | null;
    end_at: string | null;
    all_day: boolean;
    location: string;
    organizer_email: string | null;
    is_organizer: boolean;
    my_rsvp_status: string;
    meeting_link: string | null;
    calendar_link: string | null;
    importance: string;
};

export type EmailMessage = {
    message_id: string;
    folder: string;
    subject: string;
    from_addr: string;
    unread: boolean;
    is_addressed_to_me: boolean;
    from_important_sender: boolean;
    related_jira_keys: string[];
    action_required: boolean;
    received_at: string | null;
};

// ---------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------

export async function getDashboardSummary(): Promise<DashboardSummary> {
    return authedFetch<DashboardSummary>(
        "/api/dashboard/summary"
    );
}

export async function getHealth(): Promise<HealthResponse> {
    let res: Response;

    try {
        res = await fetch(`${API_BASE_URL}/health`, {
            cache: "no-store",
        });
    } catch (err) {
        throw new BackendUnavailableError(
            err instanceof Error
                ? err.message
                : "Could not reach backend"
        );
    }

    if (!res.ok) {
        throw new Error(`Health check failed: ${res.status}`);
    }

    return res.json();
}

// ---------------------------------------------------------------------
// AI
// ---------------------------------------------------------------------

export async function getDailyBriefing(): Promise<DailyBriefing> {
    return authedFetch<DailyBriefing>(
        "/api/ai/daily-briefing"
    );
}

export async function regenerateDailyBriefing(): Promise<DailyBriefing> {
    return authedFetch<DailyBriefing>(
        "/api/ai/daily-briefing/regenerate",
        {
            method: "POST",
        }
    );
}

// ---------------------------------------------------------------------
// On-demand detail fetchers
// These are intended to be called through /api/bff/* route handlers.
// ---------------------------------------------------------------------

export async function getActionFeed(): Promise<ActionItem[]> {
    return authedFetch<ActionItem[]>("/api/actions/feed");
}

export async function getCalendarEvents(): Promise<CalendarEvent[]> {
    return authedFetch<CalendarEvent[]>(
        "/api/calendar/events?upcoming_only=true"
    );
}

export async function getGmailUnread(): Promise<EmailMessage[]> {
    return authedFetch<EmailMessage[]>(
        "/api/gmail/unread?limit=20"
    );
}

export async function getGmailActionRequired(): Promise<EmailMessage[]> {
    return authedFetch<EmailMessage[]>(
        "/api/gmail/action-required?limit=20"
    );
}

export async function getJiraIssues(): Promise<JiraIssue[]> {
    return authedFetch<JiraIssue[]>("/api/jira/issues");
}

export async function getMyOpenMergeRequests(): Promise<GitLabMergeRequest[]> {
    return authedFetch<GitLabMergeRequest[]>(
        "/api/gitlab/merge-requests/mine"
    );
}

export async function getMergeRequestsToReview(): Promise<GitLabMergeRequest[]> {
    return authedFetch<GitLabMergeRequest[]>(
        "/api/gitlab/merge-requests/to-review"
    );
}

export async function getTestExecutions(): Promise<TestExecution[]> {
    return authedFetch<TestExecution[]>(
        "/api/tests/executions"
    );
}