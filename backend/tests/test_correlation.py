from app.services.correlation import extract_jira_keys


def test_extracts_single_key_from_title():
    assert extract_jira_keys("Fix login bug QA-1234") == {"QA-1234"}


def test_extracts_multiple_keys_across_fields():
    keys = extract_jira_keys("Add feature QA-1234", "Relates to TEST-9876 as well", None)
    assert keys == {"QA-1234", "TEST-9876"}


def test_extracts_from_branch_name():
    assert extract_jira_keys("feature/QA-4321-add-retry-logic") == {"QA-4321"}


def test_ignores_lowercase_and_non_matching_text():
    assert extract_jira_keys("no ticket referenced here") == set()
    assert extract_jira_keys("qa-1234 lowercase should not match") == set()


def test_dedupes_repeated_keys():
    assert extract_jira_keys("QA-1234 mentioned twice: QA-1234") == {"QA-1234"}


def test_handles_none_and_empty_strings():
    assert extract_jira_keys(None, "", None) == set()
