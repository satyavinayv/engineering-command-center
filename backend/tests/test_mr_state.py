from app.services.mr_state import compute_mr_state

AUTHOR = {"username": "alice"}
REVIEWER = {"username": "bob"}


def base_mr(**overrides):
    mr = {
        "state": "opened",
        "draft": False,
        "author": AUTHOR,
        "reviewers": [REVIEWER],
        "_notes": [],
        "_approvals": {},
        "_pipelines": [],
    }
    mr.update(overrides)
    return mr


def test_merged_state_wins_regardless_of_everything_else():
    mr = base_mr(state="merged", _pipelines=[{"status": "failed"}])
    assert compute_mr_state(mr) == "MERGED"


def test_closed_state():
    assert compute_mr_state(base_mr(state="closed")) == "CLOSED"


def test_draft_state():
    assert compute_mr_state(base_mr(draft=True)) == "DRAFT"


def test_pipeline_failed_state():
    mr = base_mr(_pipelines=[{"status": "failed", "created_at": "2026-01-01T00:00:00Z"}])
    assert compute_mr_state(mr) == "PIPELINE_FAILED"


def test_reviewer_action_required_when_reviewer_commented_last():
    mr = base_mr(
        _notes=[
            {"author": AUTHOR, "created_at": "2026-01-01T00:00:00", "system": False},
            {"author": REVIEWER, "created_at": "2026-01-02T00:00:00", "system": False},
        ]
    )
    assert compute_mr_state(mr) == "REVIEWER_ACTION_REQUIRED"


def test_not_reviewer_action_required_when_author_replied_last():
    mr = base_mr(
        _notes=[
            {"author": REVIEWER, "created_at": "2026-01-01T00:00:00", "system": False},
            {"author": AUTHOR, "created_at": "2026-01-02T00:00:00", "system": False},
        ]
    )
    assert compute_mr_state(mr) == "WAITING_FOR_REVIEWER"


def test_waiting_for_pipeline():
    mr = base_mr(_pipelines=[{"status": "running", "created_at": "2026-01-01T00:00:00Z"}])
    assert compute_mr_state(mr) == "WAITING_FOR_PIPELINE"


def test_approved_state():
    mr = base_mr(_approvals={"approved": True})
    assert compute_mr_state(mr) == "APPROVED"


def test_waiting_for_reviewer_default_when_reviewers_assigned():
    assert compute_mr_state(base_mr()) == "WAITING_FOR_REVIEWER"


def test_open_state_when_no_reviewers_assigned():
    assert compute_mr_state(base_mr(reviewers=[])) == "OPEN"


def test_system_notes_are_ignored_for_reviewer_action():
    mr = base_mr(
        _notes=[
            {"author": AUTHOR, "created_at": "2026-01-01T00:00:00", "system": False},
            {"author": REVIEWER, "created_at": "2026-01-02T00:00:00", "system": True},
        ]
    )
    # The only non-system note is from the author, so no action is pending.
    assert compute_mr_state(mr) == "WAITING_FOR_REVIEWER"
