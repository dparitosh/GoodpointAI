"""Append-only audit log for MCP migration actions.

We persist audit events into the generic `reports` table (PersistedReport) so we
avoid schema migrations.

Design goals:
- Append-only (never update existing audit events)
- Best-effort (audit failures should not break primary actions)
- Include run_id + action + timestamp + optional actor/details
"""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.report_models import PersistedReport


_AUDIT_REPORT_TYPE = "mcp_audit_event"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit_event(
    db: Session,
    *,
    run_id: Optional[str],
    action: str,
    actor: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a single audit event.

    This function is best-effort and never raises.
    """
    try:
        event_id = uuid.uuid4().hex
        payload: dict[str, Any] = {
            "event_id": event_id,
            "at": _utcnow_iso(),
            "run_id": run_id,
            "action": (action or "").strip() or "unknown",
            "actor": (actor or "").strip() or None,
            "details": dict(details or {}),
        }

        row = PersistedReport(
            id=event_id,
            report_type=_AUDIT_REPORT_TYPE,
            title=payload["action"],
            description=None,
            source=payload.get("actor"),
            schema_version="1",
            run_id=(str(run_id).strip() if run_id else None),
            external_id=None,
            table_name=None,
            payload=payload,
            summary={
                "action": payload["action"],
                "actor": payload.get("actor"),
            },
            is_deleted=0,
        )
        db.add(row)
        db.commit()
    except SQLAlchemyError:
        try:
            db.rollback()
        except Exception:  # pragma: no cover
            pass
    except Exception:  # pragma: no cover
        # best-effort: never raise
        pass
