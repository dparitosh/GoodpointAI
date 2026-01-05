from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.db_session import get_db, redacted_database_url, verify_database_connectivity
from models.report_models import PersistedReport

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _require_db() -> None:
    err = verify_database_connectivity(timeout_s=3.0)
    if err:
        raise HTTPException(
            status_code=503,
            detail=f"Database is unavailable: {err} (DATABASE_URL={redacted_database_url()})",
        )


class ReportCreateRequest(BaseModel):
    report_type: str = Field(min_length=1, max_length=64)

    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None

    source: Optional[str] = Field(default=None, max_length=64)
    schema_version: Optional[str] = Field(default=None, max_length=32)

    run_id: Optional[str] = Field(default=None, max_length=64)
    external_id: Optional[str] = Field(default=None, max_length=128)
    table_name: Optional[str] = Field(default=None, max_length=128)

    payload: Dict[str, Any]
    summary: Optional[Dict[str, Any]] = None


class ReportListItem(BaseModel):
    id: str
    report_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    schema_version: Optional[str] = None

    run_id: Optional[str] = None
    external_id: Optional[str] = None
    table_name: Optional[str] = None

    summary: Optional[Dict[str, Any]] = None
    created_at: datetime


class ReportDetail(ReportListItem):
    payload: Dict[str, Any]


@router.post("", response_model=ReportDetail)
def create_report(request: ReportCreateRequest, db: Session = Depends(get_db)) -> ReportDetail:
    _require_db()

    report_id = uuid.uuid4().hex

    row = PersistedReport(
        id=report_id,
        report_type=request.report_type,
        title=(request.title or None),
        description=(request.description or None),
        source=(request.source or None),
        schema_version=(request.schema_version or None),
        run_id=(request.run_id or None),
        external_id=(request.external_id or None),
        table_name=(request.table_name or None),
        payload=dict(request.payload or {}),
        summary=(dict(request.summary) if isinstance(request.summary, dict) else None),
        is_deleted=0,
    )

    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to persist report: {exc}") from exc

    return ReportDetail(
        id=row.id,
        report_type=row.report_type,
        title=row.title,
        description=row.description,
        source=row.source,
        schema_version=row.schema_version,
        run_id=row.run_id,
        external_id=row.external_id,
        table_name=row.table_name,
        summary=row.summary,
        created_at=row.created_at,
        payload=row.payload,
    )


@router.get("", response_model=List[ReportListItem])
def list_reports(
    report_type: Optional[str] = Query(default=None),
    run_id: Optional[str] = Query(default=None),
    external_id: Optional[str] = Query(default=None),
    table_name: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[ReportListItem]:
    _require_db()

    try:
        q = db.query(PersistedReport).filter(PersistedReport.is_deleted == 0)
        if report_type:
            q = q.filter(PersistedReport.report_type == report_type)
        if run_id:
            q = q.filter(PersistedReport.run_id == run_id)
        if external_id:
            q = q.filter(PersistedReport.external_id == external_id)
        if table_name:
            q = q.filter(PersistedReport.table_name == table_name)
        if source:
            q = q.filter(PersistedReport.source == source)

        rows = (
            q.order_by(PersistedReport.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    return [
        ReportListItem(
            id=r.id,
            report_type=r.report_type,
            title=r.title,
            description=r.description,
            source=r.source,
            schema_version=r.schema_version,
            run_id=r.run_id,
            external_id=r.external_id,
            table_name=r.table_name,
            summary=r.summary,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: str, db: Session = Depends(get_db)) -> ReportDetail:
    _require_db()

    try:
        row = (
            db.query(PersistedReport)
            .filter(PersistedReport.id == report_id)
            .filter(PersistedReport.is_deleted == 0)
            .first()
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportDetail(
        id=row.id,
        report_type=row.report_type,
        title=row.title,
        description=row.description,
        source=row.source,
        schema_version=row.schema_version,
        run_id=row.run_id,
        external_id=row.external_id,
        table_name=row.table_name,
        summary=row.summary,
        created_at=row.created_at,
        payload=row.payload,
    )


class ReportDeleteResponse(BaseModel):
    id: str
    deleted: bool


@router.delete("/{report_id}", response_model=ReportDeleteResponse)
def delete_report(report_id: str, db: Session = Depends(get_db)) -> ReportDeleteResponse:
    _require_db()

    row = db.query(PersistedReport).filter(PersistedReport.id == report_id).first()
    if row is None or int(row.is_deleted or 0) == 1:
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        row.is_deleted = 1
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete report: {exc}") from exc

    return ReportDeleteResponse(id=row.id, deleted=True)
