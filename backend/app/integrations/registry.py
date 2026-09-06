"""
Central registry of integration instances. This is the one place that
knows which integrations exist and lets the rest of the app (health
endpoint, sync engine, API routes) iterate over them uniformly, and lets
you enable/disable one independently without touching other code
(spec: "Keep the architecture modular so each integration can be
independently enabled/disabled.").

Real integrations (Jira, GitLab, Gmail, Calendar, OpenSearch) get
registered here as they're built in later phases. Phase 1 registers only
the MockIntegration so the framework itself can be exercised and tested.
"""
from app.integrations.base import Integration
from app.integrations.gitlab_integration import GitLabIntegration
from app.integrations.jira_integration import JiraIntegration
from app.integrations.mock_integration import MockIntegration
from app.integrations.opensearch_integration import OpenSearchIntegration


class IntegrationRegistry:
    def __init__(self) -> None:
        self._integrations: dict[str, Integration] = {}

    def register(self, integration: Integration) -> None:
        self._integrations[integration.key] = integration

    def get(self, key: str) -> Integration | None:
        return self._integrations.get(key)

    def all(self) -> list[Integration]:
        return list(self._integrations.values())


def build_registry() -> IntegrationRegistry:
    registry = IntegrationRegistry()
    registry.register(MockIntegration())
    registry.register(JiraIntegration())
    registry.register(GitLabIntegration())
    registry.register(OpenSearchIntegration())
    # Phase 4: registry.register(CalendarIntegration(settings))
    # Phase 5: registry.register(GmailIntegration(settings))
    return registry


registry = build_registry()
