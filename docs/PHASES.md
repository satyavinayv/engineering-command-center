# Build Phases

We build and verify one phase at a time on `dev`, then merge to `main`
once you've confirmed it runs. Nothing starts on the next phase until the
current one is checked off.

- [x] **Phase 1 — Foundation**
  Backend (FastAPI) + Frontend (Next.js) skeleton, SQLite database,
  integration abstraction + registry + mock integration, config loading,
  `/health` endpoint, basic dashboard shell showing integration health.

- [x] **Phase 2 — Jira + GitLab**
  Real Jira (PAT/Bearer, self-hosted) and GitLab (PAT, self-hosted)
  integrations, polling sync engine with persisted cursors, DB-backed
  `jira_issues`/`gitlab_merge_requests`/`gitlab_comments`/
  `gitlab_pipelines`/`entity_relationships` tables, deterministic MR
  state machine, deterministic reviewer/author/bot/system comment
  classification, deterministic Jira-key extraction + correlation,
  `/api/jira/issues`, `/api/gitlab/merge-requests/{mine,to-review,{id}}`,
  manual `/api/sync/{key}` trigger, dashboard sections for Jira work and
  both GitLab MR views.
  **Noted, not yet built:** Jenkins (PAT) — new integration you added
  mid-project, not in the original spec. Likely lands alongside
  OpenSearch in Phase 3 since Jenkins builds are probably what trigger
  the automation runs OpenSearch stores results for.

- [~] **Phase 3 — OpenSearch / Test correlation** (built, pending one confirmation from you)
  OpenSearch integration querying the single latest execution per known
  Xray test case (Jira issues with `issue_type` in
  `OPENSEARCH_TEST_ISSUE_TYPES`, default "Test"). Query matches the
  payload you gave, with one addition: an explicit `sort` by
  `@timestamp desc` — your original had `"size": 1` with no sort, which
  returns an arbitrary matching doc rather than the latest one.
  `test_executions` table stores the full raw `_source` JSON always
  (so nothing is lost), plus best-effort `status`/`test_method`/
  `test_class` extraction. GitLab MR detail view now embeds linked test
  case status directly (the "MR → Jira → Test Case → OpenSearch" chain
  from spec sections 10/24). `/api/tests/executions` powers the
  Automation Test Status dashboard section.
  **Blocking open item:** `OPENSEARCH_STATUS_FIELD` is blank — I don't
  know which field in your `_source` document holds PASS/FAIL. Paste
  one real hit's `_source` JSON (redact anything sensitive) and I'll
  set it correctly. Until then the dashboard shows "status field not
  mapped yet" instead of guessing.
  **Also unconfirmed:** whether the endpoint needs SSL verification
  disabled (self-signed cert) and whether you have a Kibana/OpenSearch
  Dashboards URL template for direct links to an execution.

- [x] **Phase 4 — Calendar** (pivoted approach — see below)
  Google Calendar API and CalDAV both turned out to require an OAuth
  app via Google Cloud Console, which is blocked by org policy, and
  there's no private "secret address in iCal format" URL available
  either (disabled by the Workspace admin). So this integration works
  by periodic **.ics export/import** instead: export from Google
  Calendar (Settings → Import & export), drop the file in
  `CALENDAR_ICS_IMPORT_DIR` or `POST /api/calendar/import`, and it's
  parsed and persisted the same way every other integration's data
  ends up in the DB. "Sync" here means "process any new .ics file",
  not polling an API. No RSVP write-back (same OAuth blocker) — a
  reliable link to the real Google Calendar event is provided instead
  (spec section 6D's documented fallback).
  Distinguishes created-by-me / accepted / pending-response, and
  deterministically flags important meetings (manager as organizer or
  attendee, or a title keyword match).
  **Fixed during review:** `is_configured()` now also requires
  `CALENDAR_PRIMARY_EMAIL` — without it, RSVP status and organizer
  detection silently produced wrong output while still reporting
  "configured." Also normalized datetime handling to naive UTC to
  match the rest of the codebase.

- [x] **Phase 5 — Gmail**
  IMAP + App Password, 2-day sync window, custom label support,
  deterministic action-required/Jira-link/GitLab-link classification.
  Header-only IMAP fetch (`BODY.PEEK[HEADER]`, not full body) for speed
  — trade-off: `snippet` is always empty, so Jira/GitLab link detection
  only scans the Subject line, not the body. Worth knowing, not
  necessarily worth changing given the stated priority on speed.
  **Fixed during review:** the UID-cursor tracking read `message.get("_uid")`
  but the field was actually stored as `"uid"` — this silently broke
  incremental sync (every run fell back to re-scanning the full date
  window instead of only what's new). One-line fix; cursor now
  advances correctly.

- [x] **Phase 6 — Unified Action Engine**
  `app/services/priority_engine.py` (pure, deterministic P0-P3 rules -
  22 hand-verified assertions) + `app/services/action_engine.py`
  (aggregates GitLab/Jira/Calendar/Gmail/test-execution data already in
  the DB into one sorted list). `GET /api/actions/required` (P0-P2, the
  "respond now" feed) and `GET /api/actions/feed` (everything, spec
  section 14's broader activity feed). No live calls, no AI - purely
  deterministic, computed on read (fast enough at single-user scale to
  not need its own persisted table).
  **Known limitation:** the "current sprint" boost from the Jira JQL
  isn't replicated here - we don't sync Jira's sprint field or the
  "Work Type" custom field (see Phase 3's OpenSearch status-field note
  for the same class of gap), so the P1 boost only uses the two
  conditions we do have data for: reporter = vaultAFTUser AND issue
  type in (Automation, Defect). Close enough for now; tell me the
  sprint custom field ID if you want it exact.

- [x] **Phase 7 — AI layer**
  `app/ai/provider.py` (swappable Mock/OpenAI `AIProvider`, works fully
  disabled), `app/ai/context_builder.py` (the privacy/speed-critical
  piece: caps input at 30 items, sends only `priority/source/title`
  strings from the already-computed action feed - never raw emails,
  Jira bodies, or DB dumps), `app/services/ai_summary.py` (caches by
  content hash of the action-item list, so the AI is only called when
  something actually changed), background scheduler job that
  pre-generates the briefing every `AI_SUMMARY_INTERVAL_MINUTES` so the
  dashboard read is always instant. `GET /api/ai/daily-briefing` +
  `POST /api/ai/daily-briefing/regenerate`.
  **Not yet built:** natural-language search, correlation fallback
  (spec section 17) - deferred until the action feed itself has been
  used for a while and proven useful; no sense building NL search over
  data you haven't validated the shape of yet.

- [ ] **Frontend** (in progress)
  Backend for every phase above is done and API-complete. Dashboard UI
  currently only has System Health, Jira, GitLab (mine/to-review), and
  Automation Test Status sections from earlier phases. Still needed:
  Action Required (top of page), AI Daily Briefing, Calendar, Gmail.

## Open questions to resolve before their phase starts

- ~~**Phase 4 (Calendar)**~~ — resolved: Google Workspace, no live API
  access possible (see Phase 4 note above) — using .ics import instead.
- ~~**Phase 2 (Jira/GitLab)**~~ — resolved: both self-hosted, VPN-only,
  PAT auth. Practical implication: the background scheduler will start
  logging auth/connection errors to `sync_status` (visible on
  `/health`) any time you're off VPN — that's expected, not a bug, and
  clears itself once you reconnect and the next sync interval fires (or
  you hit `/api/sync/jira` / `/api/sync/gitlab` manually).
- **Jenkins (PAT)** — added by you mid-project, not in the original
  spec. Needs its own decision: what should the dashboard actually show
  from Jenkins (build status per MR? per Jira issue? a separate
  "Builds" section)? Still undecided.
- **Mobile**: revisit once Phase 1–6 are solid — likely a lightweight
  read-only PWA against the same backend, tunneled via something like
  Tailscale, per the VPN note in the README.