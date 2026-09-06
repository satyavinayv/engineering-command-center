# Architecture

## Principle

Deterministic integrations first, AI second. See root README.

## Components

```
Next.js Frontend  --REST-->  FastAPI Backend  --SQLAlchemy-->  SQLite/Postgres
                                    |
                          Integration Framework
                                    |
              +------+------+------+------+---------+
              Gmail  Cal    Jira   GitLab  OpenSearch (Xray derived from Jira/GitLab)
                                    |
                          APScheduler background jobs
                          (Phase 2+: webhooks for GitLab)
```

## Integration abstraction

Every integration implements the same interface
(`backend/app/integrations/base.py`):

- `authenticate()`
- `test_connection()`
- `fetch_initial_data()`
- `incremental_sync()`
- `get_item(item_id)`
- `search(query)`
- `health_check()`

This lets each integration be enabled/disabled independently, tested with
a mock implementation (`mock_integration.py` is the reference/test
double), and swapped without touching the API or frontend layers.

## Database

Phase 1 ships the `users`, `integrations`, and `sync_status` tables —
enough to register integrations and track their health. Later phases add
`emails`, `calendar_events`, `jira_issues`, `jira_comments`,
`gitlab_merge_requests`, `gitlab_reviews`, `gitlab_comments`,
`gitlab_pipelines`, `test_cases`, `test_executions`,
`entity_relationships`, `notifications`, `actions`, `ai_summaries`,
`ai_classifications` — matching section 21 of the original spec.

Every synced row carries `source`, `source_id`, `last_synced_at` so
re-syncing never duplicates data.

## Config

`backend/app/config.py` loads settings from environment variables (via
`.env`, never committed). Nothing is hard-coded. As each integration is
added, its own env vars (e.g. `GMAIL_USERNAME`, `GMAIL_APP_PASSWORD`,
`JIRA_BASE_URL`, `JIRA_API_TOKEN`, ...) get added to `.env.example`.

## Health monitoring

`GET /health` reads exclusively from the `sync_status` table — it never
calls Jira/GitLab/etc. live. Health always reflects the last completed
background sync. This matters: an earlier version of this endpoint
called each integration's live `health_check()` on every request, which
both violated the "dashboard never depends on live external calls"
principle (section 36) and made local test runs flaky depending on
VPN/credential state. For a deliberate on-demand check (e.g. an admin
"Test Connection" button), use `POST /config/test-connection/{key}` —
that's the one place in the app allowed to make a synchronous live call,
because the user explicitly asked for it.

## AI layer (not yet built — Phase 7)

Will sit behind `AIProvider` abstraction (OpenAI / local / mock), called
asynchronously after the dashboard has already rendered from the
database, with a context-builder that sends only the minimum relevant
fields to the provider — never raw email/Jira/GitLab dumps.
