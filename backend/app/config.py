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
    jira_email: str = ""
    jira_api_token: str = ""
    jira_jql: str = "assignee = currentUser() OR reporter = currentUser()"

    gitlab_base_url: str = ""
    gitlab_personal_access_token: str = ""
    gitlab_project_ids: str = ""

    opensearch_host: str = ""
    opensearch_username: str = ""
    opensearch_password: str = ""

    calendar_provider: str = ""

    # Sync intervals (minutes) - configurable per section 33 of the spec
    sync_interval_gmail: int = 5
    sync_interval_calendar: int = 5
    sync_interval_jira: int = 5
    sync_interval_gitlab: int = 5
    sync_interval_opensearch: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
