"""
Deterministic comment classification (spec section 8). Distinguishes a
comment from an actually-assigned reviewer from a general comment, the
MR's own author, a bot, or a GitLab system note — so "reviewer commented
on your MR" notifications aren't triggered by noise.
"""

REVIEWER_COMMENT = "REVIEWER_COMMENT"
AUTHOR_COMMENT = "AUTHOR_COMMENT"
BOT_COMMENT = "BOT_COMMENT"
SYSTEM_COMMENT = "SYSTEM_COMMENT"
GENERAL_COMMENT = "GENERAL_COMMENT"


def classify_comment(note: dict, mr: dict) -> str:
    if note.get("system"):
        return SYSTEM_COMMENT

    author = note.get("author") or {}
    username = author.get("username") or ""

    if author.get("bot") or username.endswith("-bot") or "bot" in username.lower():
        return BOT_COMMENT

    mr_author_username = (mr.get("author") or {}).get("username")
    if username == mr_author_username:
        return AUTHOR_COMMENT

    reviewer_usernames = {r.get("username") for r in (mr.get("reviewers") or [])}
    if username in reviewer_usernames:
        return REVIEWER_COMMENT

    return GENERAL_COMMENT
