# Build Phases

We build and verify one phase at a time on `dev`, then merge to `main`
once you've confirmed it runs. Nothing starts on the next phase until the
current one is checked off.

- [x] **Phase 1 — Foundation**
  Backend (FastAPI) + Frontend (Next.js) skeleton, SQLite database,
  integration abstraction + registry + mock integration, config loading,
  `/health` endpoint, basic dashboard shell showing integration health.

- [ ] **Phase 2 — Jira + GitLab**
  Real Jira and GitLab integrations, sync engine (polling to start),
  reviewer-comment detection, MR state machine, Jira↔GitLab correlation.

- [ ] **Phase 3 — OpenSearch / Test correlation**
  Xray/test-id extraction engine, OpenSearch integration, Jira → MR →
  Test Case → Execution chain, pass/fail dashboard section.

- [ ] **Phase 4 — Calendar**
  Calendar integration (API TBD — see note below), created/accepted/
  pending-RSVP views, importance rules.

- [ ] **Phase 5 — Gmail**
  IMAP + app-password integration, unread/action-required/related-to-
  Jira-or-GitLab classification (deterministic first).

- [ ] **Phase 6 — Unified Action Engine**
  Cross-source Action Required feed + deterministic priority engine
  (P0–P3) + unified activity feed + notifications.

- [ ] **Phase 7 — AI layer**
  AIProvider abstraction, async summaries, daily briefing,
  natural-language search, correlation fallback — all clearly marked as
  AI-generated and never authoritative.

## Open questions to resolve before their phase starts

- **Phase 4 (Calendar)**: what actually backs your org calendar —
  Google Workspace, Microsoft 365/Exchange, or something else? This
  decides the API we integrate with (no private iCal URL assumed).
- **Phase 2 (Jira/GitLab)**: is this a self-hosted GitLab/Jira instance
  reachable only over VPN, or cloud-hosted (atlassian.net /
  gitlab.com)? Affects auth (PAT vs OAuth) and whether sync can run at
  all when you're off VPN.
- **Mobile**: revisit once Phase 1–6 are solid — likely a lightweight
  read-only PWA against the same backend, tunneled via something like
  Tailscale, per the VPN note in the README.
