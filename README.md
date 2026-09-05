# Engineering Command Center

A personal, single-user dashboard that unifies Gmail, Calendar, Jira, GitLab,
OpenSearch and Xray/test-case data into one place, so you can answer:
"What do I need to work on right now?" without opening five different tools.

## Core principle

**Deterministic integrations first. AI second.**
Every integration syncs into Postgres/SQLite on its own schedule. The
dashboard always reads from the local database, never live from an
external API or an LLM. AI (when enabled) only summarizes, classifies,
prioritizes or answers natural-language questions on top of data that is
already there — and it runs asynchronously, in the background, and is
never a hard dependency.

See `docs/ARCHITECTURE.md` for the full design and `docs/PHASES.md` for
the build plan and current status.

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, APScheduler (for
  background sync jobs), SQLite by default (swap-in Postgres later — the
  ORM layer doesn't change).
- **Frontend**: Next.js (App Router) + TypeScript.
- **No Docker** — everything runs directly on your laptop with a
  virtualenv + Node. This also means it's straightforward to later wrap
  the frontend as a mobile-friendly PWA for when you're off the company
  VPN (it'll show you whatever the laptop last synced — see note below).

## Running it (Phase 1)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in values as integrations are added
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/health` — you should see a JSON status page.
Interactive API docs: `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` — you should see the dashboard shell
pulling the health status from the backend.

## A note on VPN / mobile

Jira, GitLab (and possibly your org's calendar/mail) likely only respond
when your laptop is on the company VPN. The architecture handles this by
design: **only the laptop backend talks to those APIs.** The database is
the single source of truth the frontend reads from. When we get to the
mobile piece, it will either:
1. Point at the laptop's backend over your home network / a tunnel
   (e.g. Tailscale) while the laptop is on and synced, or
2. Read a periodically-pushed snapshot (e.g. to a small cloud DB) so it
   works even when the laptop is off.
We'll decide which when we reach that phase — flagging it now so it
shapes the sync design from the start.

## Git workflow

- `main` — clean, verified, working code only. Nothing lands here until
  you've run it and confirmed it works.
- `dev` — active work-in-progress for the phase currently being built.

Typical flow per phase:
```bash
git checkout dev
# ... build the phase, commit as you go ...
git checkout main
git merge dev
git tag phase-1-foundation
git checkout dev
```

## Phases

See `docs/PHASES.md`. We build and verify one phase at a time — nothing
jumps ahead until the current phase runs cleanly for you.
