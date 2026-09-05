from app.integrations.mock_integration import MockIntegration


def test_mock_integration_health_check_when_healthy():
    integration = MockIntegration(always_healthy=True)
    status = integration.health_check()
    assert status.connected is True
    assert status.key == "mock"


def test_mock_integration_health_check_when_unhealthy():
    integration = MockIntegration(always_healthy=False)
    status = integration.health_check()
    assert status.connected is False


def test_fetch_initial_data_returns_sync_result():
    integration = MockIntegration()
    result = integration.fetch_initial_data(window_days=7)
    assert result.records_fetched >= 1
    assert result.records_new >= 1


def test_search_is_deterministic_keyword_match():
    integration = MockIntegration()
    results = integration.search("example")
    assert len(results) == 1
    assert results[0]["id"] == "MOCK-1"

    assert integration.search("nonexistent") == []


def test_get_item_returns_none_for_unknown_id():
    integration = MockIntegration()
    assert integration.get_item("DOES-NOT-EXIST") is None
