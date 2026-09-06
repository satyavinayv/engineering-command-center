"""
Deterministic MR state machine (spec section 9). Computed purely from
GitLab API fields — never AI. Expects the raw GitLab merge_request
payload enriched with three extra keys the sync layer attaches:
`_notes` (list of note objects), `_approvals` (approvals object),
`_pipelines` (list of pipeline objects, most recent first).
"""

STATE_MERGED = "MERGED"
STATE_CLOSED = "CLOSED"
STATE_DRAFT = "DRAFT"
STATE_PIPELINE_FAILED = "PIPELINE_FAILED"
STATE_REVIEWER_ACTION_REQUIRED = "REVIEWER_ACTION_REQUIRED"
STATE_WAITING_FOR_PIPELINE = "WAITING_FOR_PIPELINE"
STATE_APPROVED = "APPROVED"
STATE_WAITING_FOR_REVIEWER = "WAITING_FOR_REVIEWER"
STATE_OPEN = "OPEN"


def has_unresolved_reviewer_action(mr: dict) -> bool:
    """True when the most recent human comment came from an assigned
    reviewer (not the author) and hasn't been followed by anything from
    the author since — i.e. the ball is in the author's court."""
    notes = [n for n in (mr.get("_notes") or []) if not n.get("system")]
    if not notes:
        return False
    notes_sorted = sorted(notes, key=lambda n: n.get("created_at", ""))
    last_note = notes_sorted[-1]
    author_username = (mr.get("author") or {}).get("username")
    reviewer_usernames = {r.get("username") for r in (mr.get("reviewers") or [])}
    last_note_author = (last_note.get("author") or {}).get("username")
    return last_note_author in reviewer_usernames and last_note_author != author_username


def compute_mr_state(mr: dict) -> str:
    if mr.get("state") == "merged":
        return STATE_MERGED
    if mr.get("state") == "closed":
        return STATE_CLOSED
    if mr.get("draft") or mr.get("work_in_progress"):
        return STATE_DRAFT

    pipelines = mr.get("_pipelines") or []
    latest_pipeline_status = pipelines[0].get("status") if pipelines else None

    if latest_pipeline_status == "failed":
        return STATE_PIPELINE_FAILED

    if has_unresolved_reviewer_action(mr):
        return STATE_REVIEWER_ACTION_REQUIRED

    if latest_pipeline_status in ("running", "pending"):
        return STATE_WAITING_FOR_PIPELINE

    approvals = mr.get("_approvals") or {}
    if approvals.get("approved"):
        return STATE_APPROVED

    if mr.get("reviewers"):
        return STATE_WAITING_FOR_REVIEWER

    return STATE_OPEN
