"""Human-in-the-loop approvals for MCP migration operations.

We store approval requests in the generic `reports` table (PersistedReport) to
avoid schema migrations.

An approval request can be created and later approved/rejected. For operations
that require approvals, callers present an approval token.
"""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.report_models import PersistedReport


_APPROVAL_REPORT_TYPE = "mcp_approval_request"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_action(action: str) -> str:
    return (action or "").strip().lower()


def create_approval_request(
    db: Session,
    *,
    run_id: str,
    action: str,
    summary: Optional[str] = None,
    impact: Optional[Dict[str, Any]] = None,
    sample: Optional[List[Dict[str, Any]]] = None,
    requested_by: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new approval request and return its payload."""
    approval_id = uuid.uuid4().hex
    token = uuid.uuid4().hex

    payload: dict[str, Any] = {
        "approval_id": approval_id,
        "run_id": run_id,
        "action": _normalize_action(action),
        "status": "pending",
        "requested_at": _utcnow_iso(),
        "requested_by": (requested_by or "").strip() or None,
        "summary": (summary or "").strip() or None,
        "impact": dict(impact or {}),
        "sample": list(sample or []),
        "note": (note or "").strip() or None,
        "token": token,
        "decided_at": None,
        "decided_by": None,
        "decision_note": None,
    }

    try:
        row = PersistedReport(
            id=approval_id,
            report_type=_APPROVAL_REPORT_TYPE,
            title=payload["action"],
            description=payload.get("summary"),
            source=payload.get("requested_by"),
            schema_version="1",
            run_id=run_id,
            external_id=token,  # used for lookups at enforcement time
            table_name=payload["action"],
            payload=dict(payload),
            summary={"status": payload["status"], "action": payload["action"]},
            is_deleted=0,
        )
        db.add(row)
        db.commit()
    except SQLAlchemyError as exc:
        try:
            db.rollback()
        except SQLAlchemyError:  # pragma: no cover
            pass
        raise RuntimeError("Failed to persist approval request") from exc

    return payload


def list_approvals(db: Session, *, run_id: str) -> List[Dict[str, Any]]:
    try:
        rows = (
            db.query(PersistedReport)
            .filter(PersistedReport.report_type == _APPROVAL_REPORT_TYPE)
            .filter(PersistedReport.run_id == run_id)
            .filter(PersistedReport.is_deleted == 0)
            .order_by(PersistedReport.created_at.desc())
            .all()
        )
        return [dict(r.payload or {}) for r in rows]
    except SQLAlchemyError:
        return []


def get_approval_by_id(db: Session, *, run_id: str, approval_id: str) -> Optional[PersistedReport]:
    try:
        return (
            db.query(PersistedReport)
            .filter(PersistedReport.id == approval_id)
            .filter(PersistedReport.report_type == _APPROVAL_REPORT_TYPE)
            .filter(PersistedReport.run_id == run_id)
            .filter(PersistedReport.is_deleted == 0)
            .first()
        )
    except SQLAlchemyError:
        return None


def get_approval_by_token(db: Session, *, run_id: str, token: str, action: str) -> Optional[Dict[str, Any]]:
    tok = (token or "").strip()
    if not tok:
        return None

    act = _normalize_action(action)

    try:
        row = (
            db.query(PersistedReport)
            .filter(PersistedReport.report_type == _APPROVAL_REPORT_TYPE)
            .filter(PersistedReport.run_id == run_id)
            .filter(PersistedReport.external_id == tok)
            .filter(PersistedReport.table_name == act)
            .filter(PersistedReport.is_deleted == 0)
            .first()
        )
        if row is None:
            return None
        return dict(row.payload or {})
    except SQLAlchemyError:
        return None


def decide_approval(
    db: Session,
    *,
    run_id: str,
    approval_id: str,
    decision: str,
    decided_by: Optional[str] = None,
    decision_note: Optional[str] = None,
) -> Dict[str, Any]:
    decision_norm = (decision or "").strip().lower()
    if decision_norm not in {"approved", "rejected"}:
        raise ValueError("decision must be approved|rejected")

    row = get_approval_by_id(db, run_id=run_id, approval_id=approval_id)
    if row is None:
        raise KeyError("approval not found")

    payload = dict(row.payload or {})
    payload["status"] = decision_norm
    payload["decided_at"] = _utcnow_iso()
    payload["decided_by"] = (decided_by or "").strip() or None
    payload["decision_note"] = (decision_note or "").strip() or None

    try:
        row.payload = dict(payload)
        row.summary = {"status": payload.get("status"), "action": payload.get("action")}
        row.source = payload.get("decided_by") or row.source
        db.commit()
    except SQLAlchemyError as exc:
        try:
            db.rollback()
        except SQLAlchemyError:  # pragma: no cover
            pass
        raise RuntimeError("Failed to persist approval decision") from exc

    return payload
