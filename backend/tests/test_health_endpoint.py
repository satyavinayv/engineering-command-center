"""
Health endpoint tests must never depend on the developer's local .env
(e.g. real Jira/GitLab credentials someone is actively testing with) or
on network/VPN state - that would make the test result different on
every machine. We swap in a registry containing only the deterministic
Mock integration for the duration of these tests.
"""

import pytest
from fastapi.testclient import TestClient

import app.api.routes.health as health_module
from app.integrations.mock_integration import MockIntegration
from app.main import app


class _FakeRegistry:
    def all(self):
        return [MockIntegration(always_healthy=True)]


@pytest.fixture(autouse=True)
def isolate_registry(monkeypatch):
    monkeypatch.setattr(health_module, "registry", _FakeRegistry())


def test_health_endpoint_returns_ok_with_mock_integration():
    with TestClient(app) as test_client:
        response = test_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert any(i["key"] == "mock" for i in body["integrations"])


def test_root_endpoint():
    with TestClient(app) as test_client:
        response = test_client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
