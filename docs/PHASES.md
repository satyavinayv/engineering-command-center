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

- [ ] **Phase 4 — Calendar**
  Calendar integration (API TBD — see note below), created/accepted/
  pending-RSVP views, importance rules.

- [ ] **Phase 5 — Gmail**
  IMAP + app-password integration. Sync window defaults to **2 days**
  (today + yesterday, not the spec's original 7/30/90 default) so
  today's tasks and yesterday's unfinished ones both surface. Also
  syncs your custom Gmail labels (via IMAP folders), not just the
  inbox — each label needs "Show in IMAP" enabled in Gmail settings for
  this to work. unread/action-required/related-to-Jira-or-GitLab
  classification (deterministic first).

- [ ] **Phase 6 — Unified Action Engine**
  Cross-source Action Required feed + deterministic priority engine
  (P0–P3) + unified activity feed + notifications. Priority rules will
  boost anything in the current sprint (or matching the
  vaultAFTUser/Automation-Defect/Script-Update rule from the Jira JQL)
  above equivalent non-sprint work — same "ignore Resolved/Closed/
  Running on GM" exclusions apply here too.

- [ ] **Phase 7 — AI layer**
  AIProvider abstraction, async summaries, daily briefing,
  natural-language search, correlation fallback — all clearly marked as
  AI-generated and never authoritative.

## Open questions to resolve before their phase starts

- **Phase 4 (Calendar)**: what actually backs your org calendar —
  Google Workspace, Microsoft 365/Exchange, or something else? This
  decides the API we integrate with (no private iCal URL assumed).
- ~~**Phase 2 (Jira/GitLab)**~~ — resolved: both self-hosted, VPN-only,
  PAT auth. Practical implication: the background scheduler will start
  logging auth/connection errors to `sync_status` (visible on
  `/health`) any time you're off VPN — that's expected, not a bug, and
  clears itself once you reconnect and the next sync interval fires (or
  you hit `/api/sync/jira` / `/api/sync/gitlab` manually).
- **Jenkins (PAT)** — added by you mid-project, not in the original
  spec. Needs its own decision: what should the dashboard actually show
  from Jenkins (build status per MR? per Jira issue? a separate
  "Builds" section)? Revisit when we reach Phase 3.
- **Mobile**: revisit once Phase 1–6 are solid — likely a lightweight
  read-only PWA against the same backend, tunneled via something like
  Tailscale, per the VPN note in the README.
