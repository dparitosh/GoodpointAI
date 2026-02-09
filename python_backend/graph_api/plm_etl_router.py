"""PLM ETL router (Legacy - Run Creation Only).

Most logic (staging, transform, validation) has moved to the ETL Orchestrator Agent.
This router is kept to allow the frontend to generate a valid run_id before handing off to the Agent.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.db_session import DATABASE_URL, get_db
from models.plm_models import PLMIngestionRun


router = APIRouter(prefix="/api/plm/etl", tags=["PLM - ETL"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _require_postgres() -> None:
    url = (DATABASE_URL or "").strip().lower()
    if not (url.startswith("postgresql") or url.startswith("postgres")):
        raise HTTPException(
            status_code=503,
            detail="Postgres is required for PLM ETL. Set DATABASE_URL to a Postgres connection string.",
        )


class CreateRunRequest(BaseModel):
    source_system: str = Field(..., min_length=1)
    target_system: str = Field(..., min_length=1)


class CreateRunResponse(BaseModel):
    run_id: str
    status: str
    created_at: str


@router.post("/runs", response_model=CreateRunResponse)
async def create_run(payload: CreateRunRequest, db: Session = Depends(get_db)):
    _require_postgres()

    run_id = uuid.uuid4().hex
    row = PLMIngestionRun(
        id=run_id,
        source_system=payload.source_system.strip(),
        target_system=payload.target_system.strip(),
        status="created",
    )
    db.add(row)
    db.commit()

    return CreateRunResponse(run_id=run_id, status=row.status, created_at=_utcnow_iso())
