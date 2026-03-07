"""
Reporting Hub Router — /api/report-hub
==========================================
Centralised store for reports from every dashboard page:
  POST /api/report-hub           → save a report
  GET  /api/report-hub           → list (filter by type / workflow_id / status)
  GET  /api/report-hub/summary   → aggregate KPIs
  GET  /api/report-hub/{id}      → single report detail
  DELETE /api/report-hub/{id}    → delete
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.report_hub_models import UnifiedReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report-hub", tags=["Reporting Hub"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class ReportIn(BaseModel):
    report_type: str          # migration | lineage | analytics | dq_scan | discovery | observability | self_healing
    title: str
    workflow_id: Optional[str] = None
    run_id: Optional[str] = None
    source_page: Optional[str] = None
    status: Optional[str] = "info"
    summary: Optional[dict] = None
    result: Optional[dict] = None
    tags: Optional[List[str]] = None


class ReportOut(BaseModel):
    report_id: str
    report_type: str
    title: str
    workflow_id: Optional[str]
    run_id: Optional[str]
    source_page: Optional[str]
    status: Optional[str]
    summary: Optional[dict]
    tags: Optional[List[str]]
    created_at: str

    class Config:
        from_attributes = True


class ReportDetailOut(ReportOut):
    result: Optional[dict]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=ReportDetailOut, summary="Save a report from any page")
def save_report(body: ReportIn, db: Session = Depends(get_db)):
    row = UnifiedReport(
        report_id=str(uuid.uuid4()),
        report_type=body.report_type,
        title=body.title,
        workflow_id=body.workflow_id,
        run_id=body.run_id,
        source_page=body.source_page,
        status=body.status,
        summary=body.summary,
        result=body.result,
        tags=body.tags or [],
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_detail(row)


@router.get("", response_model=List[ReportOut], summary="List all reports")
def list_reports(
    report_type: Optional[str] = Query(None),
    workflow_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(UnifiedReport)
    if report_type:
        q = q.filter(UnifiedReport.report_type == report_type)
    if workflow_id:
        q = q.filter(UnifiedReport.workflow_id == workflow_id)
    if status:
        q = q.filter(UnifiedReport.status == status)
    rows = q.order_by(UnifiedReport.created_at.desc()).limit(limit).all()
    return [_to_out(r) for r in rows]


@router.get("/summary", summary="Aggregate KPIs across all saved reports")
def reports_summary(db: Session = Depends(get_db)):
    rows = db.query(UnifiedReport).all()
    by_type: dict = {}
    by_status: dict = {}
    for r in rows:
        by_type[r.report_type] = by_type.get(r.report_type, 0) + 1
        s = r.status or "info"
        by_status[s] = by_status.get(s, 0) + 1
    return {
        "total": len(rows),
        "by_type": by_type,
        "by_status": by_status,
    }


@router.get("/{report_id}", response_model=ReportDetailOut, summary="Get a single report")
def get_report(report_id: str, db: Session = Depends(get_db)):
    row = db.query(UnifiedReport).filter(UnifiedReport.report_id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_detail(row)


@router.delete("/{report_id}", summary="Delete a report")
def delete_report(report_id: str, db: Session = Depends(get_db)):
    row = db.query(UnifiedReport).filter(UnifiedReport.report_id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(row)
    db.commit()
    return {"deleted": report_id}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_out(r: UnifiedReport) -> dict:
    return {
        "report_id": r.report_id,
        "report_type": r.report_type,
        "title": r.title,
        "workflow_id": r.workflow_id,
        "run_id": r.run_id,
        "source_page": r.source_page,
        "status": r.status,
        "summary": r.summary,
        "tags": r.tags or [],
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _to_detail(r: UnifiedReport) -> dict:
    d = _to_out(r)
    d["result"] = r.result
    return d
