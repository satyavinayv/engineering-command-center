"""
Deterministic priority engine (spec section 16). Every function here is
pure - plain inputs in, a priority label (or None, meaning "not an
action item") out. No DB, no AI, no network. This is what
action_engine.py calls per source; keeping it separate and pure means
it's fully unit-testable and it's the one place all priority rules
live, so they're easy to audit and change without touching the
DB-querying glue code.
"""

P0 = "P0"  # critical - respond now
P1 = "P1"  # today
P2 = "P2"  # this week / important
P3 = "P3"  # informational


def classify_gitlab_mr_priority(computed_state: str, is_mine: bool) -> str | None:
    """is_mine=True means you're the author; False means you're an
    assigned reviewer."""
    if is_mine and computed_state == "PIPELINE_FAILED":
        return P0
    if is_mine and computed_state == "REVIEWER_ACTION_REQUIRED":
        return P1
    if not is_mine and computed_state == "WAITING_FOR_REVIEWER":
        return P2
    return None


def classify_jira_priority(
    status: str,
    jira_priority: str,
    reporter: str | None,
    issue_type: str,
    done_statuses: list[str],
    p0_priorities: list[str],
) -> str | None:
    if status.strip().lower() in done_statuses:
        return None
    if jira_priority.strip().lower() in p0_priorities:
        return P0
    # Approximation of the "vaultAFTUser + Automation/Defect + Script
    # Update" sprint-priority bucket from JIRA_JQL - we don't sync the
    # "Work Type" custom field (see docs/PHASES.md), so this uses the
    # two conditions we do have data for.
    if reporter and reporter.strip().lower() == "vaultaftuser" and issue_type.strip().lower() in (
        "automation",
        "defect",
    ):
        return P1
    return P2


def classify_calendar_priority(is_organizer: bool, rsvp_status: str, start_at, now) -> str | None:
    """Only flags meetings you have NOT responded to yet (spec section
    6C - "especially important"). Meetings you created or already
    responded to aren't action items."""
    if is_organizer or rsvp_status != "NEEDS-ACTION":
        return None
    if start_at is None or start_at < now:
        return None
    return P1 if start_at.date() == now.date() else P2


def classify_gmail_priority(action_required: bool, from_important_sender: bool) -> str | None:
    if not action_required:
        return None
    return P1 if from_important_sender else P2


def classify_test_execution_priority(status: str | None) -> str | None:
    if status and status.strip().upper() in ("FAIL", "FAILED"):
        return P0
    return None