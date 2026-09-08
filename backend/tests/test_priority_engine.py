from datetime import datetime

from app.services.priority_engine import (
    P0,
    P1,
    P2,
    classify_calendar_priority,
    classify_gitlab_mr_priority,
    classify_gmail_priority,
    classify_jira_priority,
    classify_test_execution_priority,
)

DONE = ["resolved", "closed", "running on gm"]
P0_PRIORITIES = ["highest", "blocker", "critical"]


def test_gitlab_pipeline_failed_on_my_mr_is_p0():
    assert classify_gitlab_mr_priority("PIPELINE_FAILED", is_mine=True) == P0


def test_gitlab_reviewer_action_required_on_my_mr_is_p1():
    assert classify_gitlab_mr_priority("REVIEWER_ACTION_REQUIRED", is_mine=True) == P1


def test_gitlab_waiting_for_reviewer_when_im_the_reviewer_is_p2():
    assert classify_gitlab_mr_priority("WAITING_FOR_REVIEWER", is_mine=False) == P2


def test_gitlab_pipeline_failed_on_someone_elses_mr_is_not_my_action():
    assert classify_gitlab_mr_priority("PIPELINE_FAILED", is_mine=False) is None


def test_gitlab_approved_state_is_not_an_action_item():
    assert classify_gitlab_mr_priority("APPROVED", is_mine=True) is None


def test_jira_done_status_excluded():
    assert classify_jira_priority("Resolved", "Medium", None, "Task", DONE, P0_PRIORITIES) is None


def test_jira_highest_priority_is_p0():
    assert classify_jira_priority("In Progress", "Highest", None, "Bug", DONE, P0_PRIORITIES) == P0


def test_jira_vaultaftuser_automation_defect_is_p1():
    assert classify_jira_priority("To Do", "Medium", "vaultAFTUser", "Automation", DONE, P0_PRIORITIES) == P1
    assert classify_jira_priority("To Do", "Medium", "vaultAFTUser", "Defect", DONE, P0_PRIORITIES) == P1


def test_jira_normal_issue_is_p2():
    assert classify_jira_priority("To Do", "Medium", "someone_else", "Story", DONE, P0_PRIORITIES) == P2


def test_calendar_organizer_never_needs_rsvp_action():
    assert classify_calendar_priority(True, "NEEDS-ACTION", datetime(2026, 1, 2), datetime(2026, 1, 1)) is None


def test_calendar_already_responded_is_not_an_action():
    assert classify_calendar_priority(False, "ACCEPTED", datetime(2026, 1, 2), datetime(2026, 1, 1)) is None


def test_calendar_pending_rsvp_today_is_p1():
    now = datetime(2026, 1, 1, 9, 0)
    assert classify_calendar_priority(False, "NEEDS-ACTION", datetime(2026, 1, 1, 15, 0), now) == P1


def test_calendar_pending_rsvp_future_day_is_p2():
    now = datetime(2026, 1, 1, 9, 0)
    assert classify_calendar_priority(False, "NEEDS-ACTION", datetime(2026, 1, 5, 15, 0), now) == P2


def test_calendar_past_event_is_not_an_action():
    now = datetime(2026, 1, 5)
    assert classify_calendar_priority(False, "NEEDS-ACTION", datetime(2026, 1, 1), now) is None


def test_gmail_action_required_from_important_sender_is_p1():
    assert classify_gmail_priority(True, True) == P1


def test_gmail_action_required_from_normal_sender_is_p2():
    assert classify_gmail_priority(True, False) == P2


def test_gmail_not_action_required_is_none():
    assert classify_gmail_priority(False, True) is None


def test_test_execution_fail_is_p0():
    assert classify_test_execution_priority("FAIL") == P0
    assert classify_test_execution_priority("failed") == P0


def test_test_execution_pass_is_not_an_action():
    assert classify_test_execution_priority("PASS") is None


def test_test_execution_none_status_is_not_an_action():
    assert classify_test_execution_priority(None) is None