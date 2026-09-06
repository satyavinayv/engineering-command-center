from app.integrations.opensearch_integration import build_execution_query


def test_query_includes_sort_by_timestamp_desc():
    query = build_execution_query("TEST-9876", "GM", 90)
    assert query["sort"] == [{"@timestamp": {"order": "desc"}}]


def test_query_size_is_one():
    query = build_execution_query("TEST-9876", "GM", 90)
    assert query["size"] == 1


def test_query_filters_environment_and_xray_id():
    query = build_execution_query("TEST-9876", "GM", 90)
    filters = query["query"]["bool"]["filter"]
    assert {"match_phrase": {"environment": "GM"}} in filters
    should = filters[2]["bool"]["should"]
    assert {"match_phrase": {"x_ray_id": "TEST-9876"}} in should


def test_query_window_days_is_configurable():
    query = build_execution_query("TEST-1", "QA", 30)
    range_filter = query["query"]["bool"]["filter"][1]["range"]["@timestamp"]
    assert range_filter["gte"] == "now-30d"
