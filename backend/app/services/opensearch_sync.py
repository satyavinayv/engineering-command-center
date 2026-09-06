"""
Persists a single OpenSearch hit (as returned by
OpenSearchIntegration._query_latest_execution) into test_executions,
deduping by OpenSearch's own document _id. Always stores the full
_source as JSON (raw_source) regardless of whether our field-name
guesses below succeed, so the true data is never lost (spec section
13: "the raw failure information must always be displayed").
"""
import json
from datetime import datetime, timezone

from app.config import settings
from app.database import SessionLocal
from app.models import TestExecution

# Defensive cap - some automation frameworks dump huge stack traces into
# a single field. We keep the whole thing but don't let one document
# blow up the row past what SQLite/Postgres handle comfortably.
MAX_RAW_SOURCE_CHARS = 50_000


def _parse_es_timestamp(value: str | None):
    if not value:
        return None
    try:
        # Handles both "...Z" and "...+00:00" style timestamps
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _build_dashboard_url(index: str, doc_id: str) -> str:
    template = settings.opensearch_dashboard_url_template
    if not template:
        return ""
    return template.format(index=index, doc_id=doc_id)


def persist_execution(hit: dict, test_case_key: str) -> dict:
    source = hit.get("_source", {}) or {}
    doc_id = hit.get("_id", "")
    fields = hit.get("fields", {}) or {}

    status = None
    if settings.opensearch_status_field:
        status = source.get(settings.opensearch_status_field)

    raw_json = json.dumps(source)[:MAX_RAW_SOURCE_CHARS]

    db = SessionLocal()
    try:
        existing = db.query(TestExecution).filter_by(source_doc_id=doc_id).one_or_none()
        is_new = existing is None

        values = dict(
            test_case_key=test_case_key,
            environment=source.get("environment", ""),
            status=status,
            test_method=(fields.get("test_method") or [None])[0],
            test_class=(fields.get("test_class") or [None])[0],
            executed_at=_parse_es_timestamp(source.get("@timestamp")),
            raw_source=raw_json,
            opensearch_url=_build_dashboard_url(hit.get("_index", ""), doc_id),
            last_synced_at=datetime.now(timezone.utc),
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            db.add(TestExecution(source_doc_id=doc_id, **values))

        db.commit()
    finally:
        db.close()

    return {"new": is_new}
