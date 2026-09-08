"""
Central configuration.

Loaded once from environment variables / .env. Nothing here is
hard-coded, and this module is the ONLY place that should read
os.environ directly — everything else imports `settings` from here.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    api_key: str = "changeme-choose-a-long-random-string"

    database_url: str = "sqlite:///./eng_command_center.db"

    ai_enabled: bool = False
    ai_provider: str = "mock"
    openai_api_key: str = ""

    gmail_username: str = ""
    gmail_app_password: str = ""

    jira_base_url: str = ""
    jira_api_token: str = ""
    jira_jql: str = (
        '(assignee = currentUser() OR reporter = currentUser() OR (sprint in openSprints()) '
        'OR (reporter = "vaultAFTUser" AND issuetype in (Automation, Defect) '
        'AND "Work Type" = "Script Update")) '
        "AND status not in (Resolved, Closed, \"Running on GM\")"
    )

    gitlab_base_url: str = ""
    gitlab_personal_access_token: str = ""
    gitlab_project_ids: str = ""
    # Your GitLab username - used to filter "my open MRs" / "assigned to
    # me for review" without another API round trip.
    gitlab_username: str = ""

    opensearch_host: str = ""
    opensearch_username: str = ""
    opensearch_password: str = ""
    opensearch_index_pattern: str = "autoresult-*"
    opensearch_environment: str = "GM"
    opensearch_window_days: int = 90
    # Comma-separated Jira issue-type names that count as an Xray test
    # case (so we know which synced Jira issues to look up executions
    # for). "Test" is Xray's standard type name - adjust if yours differs.
    opensearch_test_issue_types: str = "Test"
    # Field in the OpenSearch document's _source that holds PASS/FAIL.
    # Left blank until confirmed against a real sample document - see
    # docs/PHASES.md open questions.
    opensearch_status_field: str = ""
    # Optional Kibana/OpenSearch-Dashboards URL template for linking
    # straight to an execution, e.g.
    # "https://kibana.example.com/app/discover#/doc/<pattern-id>/{index}?id={doc_id}"
    # Left blank until confirmed.
    opensearch_dashboard_url_template: str = ""
    # Self-hosted ES/OpenSearch behind VPN sometimes uses a self-signed
    # cert. Flip to False only if you hit SSL errors and know why.
    opensearch_verify_ssl: bool = True

    calendar_provider: str = ""
    # Calendar (Phase 4) — ICS-import based
    calendar_ics_import_dir: str = "./data/calendar_imports"
    calendar_primary_email: str = ""
    calendar_manager_email: str = ""
    calendar_important_keywords: str = (
        "1:1,sprint planning,retro,release,incident,postmortem"
    )

    # Gmail (Phase 5) — IMAP + App Password, no OAuth
    gmail_imap_host: str = "imap.gmail.com"
    gmail_sync_window_days: int = 2
    gmail_labels: str = ""
    gmail_important_senders: str = ""

    @property
    def gmail_labels_list(self) -> list[str]:
        return [l.strip() for l in self.gmail_labels.split(",") if l.strip()]

    @property
    def gmail_important_senders_list(self) -> list[str]:
        return [s.strip() for s in self.gmail_important_senders.split(",") if s.strip()]

    @property
    def calendar_important_keywords_list(self) -> list[str]:
        return [
            k.strip()
            for k in self.calendar_important_keywords.split(",")
            if k.strip()
        ]


    # Sync intervals (minutes) - configurable per section 33 of the spec
    sync_interval_gmail: int = 5
    sync_interval_calendar: int = 5
    sync_interval_jira: int = 5
    sync_interval_gitlab: int = 5
    sync_interval_opensearch: int = 5

    # --- Phase 6: Priority Engine (spec section 16) ---
    # Statuses that mean "done, don't surface as an action item" -
    # mirrors the JIRA_JQL exclusions so the two stay in sync.
    jira_done_statuses: str = "Resolved,Closed,Running on GM"
    # Jira priority names that always mean P0 regardless of anything else
    action_p0_jira_priorities: str = "Highest,Blocker,Critical"

    @property
    def jira_done_statuses_list(self) -> list[str]:
        return [s.strip().lower() for s in self.jira_done_statuses.split(",") if s.strip()]

    @property
    def action_p0_jira_priorities_list(self) -> list[str]:
        return [p.strip().lower() for p in self.action_p0_jira_priorities.split(",") if p.strip()]

    # --- Phase 7: AI layer ---
    openai_model: str = "gpt-4o-mini"
    # How often the background job pre-generates the daily briefing, so
    # it's already cached (instant) by the time the dashboard is opened
    # (spec section 18 - AI must never be in the critical path of a
    # dashboard load).
    ai_summary_interval_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()