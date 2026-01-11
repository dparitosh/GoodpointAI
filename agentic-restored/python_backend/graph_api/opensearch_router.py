import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.db_session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/opensearch", tags=["opensearch"])


def _load_db_config(db: Session) -> Dict[str, Any]:
    """Load OpenSearch config from encrypted DB storage.

    Falls back to environment variables if not found or decrypt fails.
    """
    try:
        from core.crypto import decrypt_json
        from models.configuration_models import EncryptedConfig

        row = db.get(EncryptedConfig, "opensearch")
        if row is None:
            return {}

        payload = decrypt_json(row.ciphertext)
        url = str(payload.get("url") or payload.get("endpoint") or "").strip()
        if not url:
            return {}

        return {
            "url": url,
            "username": payload.get("username") or None,
            "password": payload.get("password") or None,
            "verify_certs": bool(payload.get("verify_certs", True)),
            "timeout_s": float(payload.get("timeout_s", 5.0) or 5.0),
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to load OpenSearch config from DB; falling back to env: %s", exc)
        return {}


def get_service(db: Session) -> Any:
    try:
        # Reload .env so OPENSEARCH_URL changes are picked up without restart.
        from core.external_config import reload_dotenv

        reload_dotenv(override=True)

        # Do not cache: allows OPENSEARCH_URL/OPENSEARCH_HOSTS to be updated without restart.
        from services.opensearch_service import OpenSearchService

        cfg = _load_db_config(db)
        return OpenSearchService(config=cfg)
    except Exception as exc:
        logger.error("Failed to initialize OpenSearchService: %s", exc)
        raise HTTPException(status_code=500, detail="Service initialization failed") from exc


class IndexRequest(BaseModel):
    index: str = Field(..., description="Target index name")
    document: Dict[str, Any] = Field(..., description="Document body")
    id: Optional[str] = Field(default=None, description="Optional document ID")
    refresh: bool = Field(default=False, description="Refresh index after write")


class SearchRequest(BaseModel):
    query: Dict[str, Any] = Field(..., description="OpenSearch query DSL")


@router.get("/health")
async def health(db: Session = Depends(get_db)):
    service = get_service(db)
    return service.health()


@router.post("/index")
async def index_document(request: IndexRequest, db: Session = Depends(get_db)):
    service = get_service(db)
    try:
        return service.index_document(index=request.index, document=request.document, doc_id=request.id, refresh=request.refresh)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("OpenSearch index failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/search/{index}")
async def search(index: str, request: SearchRequest, db: Session = Depends(get_db)):
    """Search an OpenSearch index.
    
    Returns empty results if OpenSearch is not configured.
    """
    try:
        service = get_service(db)
        # Wrap query in proper OpenSearch body format
        body = {"query": request.query}
        return service.search(index=index, query=body)
    except RuntimeError as exc:
        # OpenSearch not configured - return empty results instead of error
        logger.info("OpenSearch not configured, returning empty results for %s", index)
        return {
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "max_score": None,
                "hits": []
            },
            "took": 0,
            "timed_out": False,
            "_shards": {"total": 0, "successful": 0, "skipped": 0, "failed": 0},
            "_mock": True,
            "_message": str(exc)
        }
    except Exception as exc:
        # If OpenSearch is configured but unreachable (timeout/connection error),
        # degrade gracefully so the UI can still function.
        try:
            from opensearchpy.exceptions import ConnectionError as OSConnectionError  # type: ignore
            from opensearchpy.exceptions import ConnectionTimeout as OSConnectionTimeout  # type: ignore
            from opensearchpy.exceptions import TransportError as OSTransportError  # type: ignore
        except Exception:  # pragma: no cover
            OSConnectionError = ()  # type: ignore
            OSConnectionTimeout = ()  # type: ignore
            OSTransportError = ()  # type: ignore

        if isinstance(exc, (OSConnectionError, OSConnectionTimeout, OSTransportError, TimeoutError, ConnectionError)):
            logger.info("OpenSearch unreachable, returning empty results for %s: %s", index, exc)
            return {
                "hits": {
                    "total": {"value": 0, "relation": "eq"},
                    "max_score": None,
                    "hits": []
                },
                "took": 0,
                "timed_out": True,
                "_shards": {"total": 0, "successful": 0, "skipped": 0, "failed": 0},
                "_mock": True,
                "_message": str(exc)
            }
        logger.error("OpenSearch search failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
