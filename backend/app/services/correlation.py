"""
Deterministic correlation engine (spec section 11). Pulls Jira-issue-
style identifiers (QA-1234, TEST-9876, ...) out of GitLab MR titles,
descriptions and branch names using plain regex — no AI involved. This
covers the "GitLab MR -> Jira issue" edge; the "Jira issue -> Xray test
case -> OpenSearch execution" chain is built in Phase 3 on top of the
same EntityRelationship table.

AI is only ever a *fallback* here (Phase 7), for cases this regex
approach misses, and even then must be marked with source="ai" and a
confidence score — never silently treated as fact (spec section 27).
"""
import re
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import EntityRelationship

# Matches typical Jira issue keys: 2+ uppercase letters/digits, dash, digits.
# e.g. QA-1234, TEST-9876, PROJ2-42. Intentionally broad; false positives
# are cheap to ignore, false negatives are not.
JIRA_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")


def extract_jira_keys(*texts: str | None) -> set[str]:
    keys: set[str] = set()
    for text in texts:
        if not text:
            continue
        keys.update(JIRA_KEY_PATTERN.findall(text))
    return keys


def correlate_merge_request(mr: dict, base_url: str) -> list[str]:
    """Extracts Jira keys from an MR's title/description/branch and
    records a deterministic gitlab_mr -> jira_issue relationship for
    each one found. Returns the keys found (for logging/tests)."""
    keys = extract_jira_keys(mr.get("title"), mr.get("description"), mr.get("source_branch"))
    if not keys:
        return []

    db = SessionLocal()
    try:
        for key in keys:
            existing = (
                db.query(EntityRelationship)
                .filter_by(
                    from_type="gitlab_mr",
                    from_key=str(mr["id"]),
                    to_type="jira_issue",
                    to_key=key,
                )
                .one_or_none()
            )
            if existing:
                continue
            db.add(
                EntityRelationship(
                    from_type="gitlab_mr",
                    from_key=str(mr["id"]),
                    to_type="jira_issue",
                    to_key=key,
                    relationship_type="mentions",
                    confidence=1.0,
                    source="deterministic",
                    created_at=datetime.now(timezone.utc),
                )
            )
        db.commit()
    finally:
        db.close()
    return sorted(keys)
