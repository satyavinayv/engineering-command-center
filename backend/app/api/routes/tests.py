"""
Read-only endpoints for the "Automation Test Status" dashboard section
(spec section 12) — always from the local DB, joined in plain Python
rather than ORM relationships since the schema deliberately stays
flat/string-keyed (spec section 38: don't overengineer a single-user
tool).
"""
import json

from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.database import SessionLocal
from app.models import EntityRelationship, JiraIssue, TestExecution

router = APIRouter(prefix="/api/tests", tags=["tests"], dependencies=[Depends(require_api_key)])


@router.get("/executions")
def list_test_executions():
    db = SessionLocal()
    try:
        executions = (
            db.query(TestExecution).order_by(TestExecution.executed_at.desc()).limit(200).all()
        )
        keys = {e.test_case_key for e in executions}

        jira_by_key = (
            {j.key: j for j in db.query(JiraIssue).filter(JiraIssue.key.in_(keys)).all()}
            if keys
            else {}
        )
        mr_ids_by_key: dict[str, list[str]] = {}
        if keys:
            rels = (
                db.query(EntityRelationship)
                .filter(EntityRelationship.to_type == "jira_issue", EntityRelationship.to_key.in_(keys))
                .all()
            )
            for r in rels:
                mr_ids_by_key.setdefault(r.to_key, []).append(r.from_key)

        result = []
        for e in executions:
            jira = jira_by_key.get(e.test_case_key)
            result.append(
                {
                    "test_case_key": e.test_case_key,
                    "jira_summary": jira.summary if jira else None,
                    "jira_url": jira.url if jira else None,
                    "linked_gitlab_mr_source_ids": mr_ids_by_key.get(e.test_case_key, []),
                    "status": e.status,  # null until OPENSEARCH_STATUS_FIELD is confirmed
                    "environment": e.environment,
                    "test_method": e.test_method,
                    "test_class": e.test_class,
                    "executed_at": e.executed_at.isoformat() if e.executed_at else None,
                    "opensearch_url": e.opensearch_url or None,
                }
            )
        return result
    finally:
        db.close()


@router.get("/executions/{test_case_key}")
def test_execution_detail(test_case_key: str):
    """Full detail for one test case, including the raw OpenSearch
    _source document - the ground truth (spec section 13), always shown
    regardless of whether our status-field guess is right."""
    db = SessionLocal()
    try:
        execution = (
            db.query(TestExecution)
            .filter_by(test_case_key=test_case_key)
            .order_by(TestExecution.executed_at.desc())
            .first()
        )
        if not execution:
            return {"error": "not found"}
        return {
            "test_case_key": execution.test_case_key,
            "status": execution.status,
            "environment": execution.environment,
            "test_method": execution.test_method,
            "test_class": execution.test_class,
            "executed_at": execution.executed_at.isoformat() if execution.executed_at else None,
            "opensearch_url": execution.opensearch_url or None,
            "raw_source": json.loads(execution.raw_source),
        }
    finally:
        db.close()
