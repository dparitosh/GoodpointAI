import logging
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_serializer
from datetime import datetime
import neo4j
from sqlalchemy.orm import Session

from core.crypto import decrypt_json, encrypt_json
from core.db_session import get_db
from models.configuration_models import DataSourceConfigRecord

# pylint: disable=broad-exception-caught

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data-sources", tags=["Data Sources"])


class SampleRecordsResponse(BaseModel):
    source_id: str
    source_type: str
    count: int
    format: str
    records: List[Dict[str, Any]]
    warnings: List[str] = []


def _workspace_root() -> Path:
    # python_backend/graph_api -> python_backend -> agentic-restored
    return Path(__file__).resolve().parents[2]


def _allowed_local_roots() -> List[Path]:
    root = _workspace_root()
    candidates = [root / "data", root / "python_backend" / "data", root.parent / "data"]

    # Admin/server-controlled allowlist (stored encrypted in DB). This keeps the
    # user-entered data source record separate from the server permission to read
    # from a local filesystem path.
    try:
        from core.config_store import get_encrypted_config_payload

        sys_cfg = get_encrypted_config_payload("system_configuration")
        allowed_list: list[object] = []
        if isinstance(sys_cfg, dict):
            roots_val = sys_cfg.get("allowed_local_roots")
            if isinstance(roots_val, list):
                allowed_list = roots_val
            else:
                fs_cfg = sys_cfg.get("filesystem")
                if isinstance(fs_cfg, dict):
                    roots_val2 = fs_cfg.get("allowed_local_roots")
                    if isinstance(roots_val2, list):
                        allowed_list = roots_val2

        for item in allowed_list:
                p = str(item).strip().strip('"')
                if not p:
                    continue
                try:
                    candidates.append(Path(p))
                except Exception:
                    continue
    except Exception:
        # Non-fatal: fall back to env + repo-local defaults.
        pass

    extra_raw = (os.getenv("GRAPH_TRACE_ALLOWED_LOCAL_ROOTS") or "").strip()
    if extra_raw:
        # Windows-friendly delimiter. Example:
        #   GRAPH_TRACE_ALLOWED_LOCAL_ROOTS=D:\some\folder;E:\other
        for item in extra_raw.split(";"):
            p = item.strip().strip('"')
            if not p:
                continue
            try:
                candidates.append(Path(p))
            except Exception:
                continue

    return [p.resolve() for p in candidates if p.exists()]


def _is_under_allowed_root(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in _allowed_local_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _detect_format_from_name(name: str) -> str:
    lower = (name or "").lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".json"):
        return "json"
    return "unknown"


def _parse_csv_bytes(content: bytes, *, limit: int) -> List[Dict[str, Any]]:
    import csv
    import io

    # Handle common UTF-8 BOM prefix written by Windows tools.
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    for row in reader:
        rows.append(dict(row))
        if len(rows) >= limit:
            break
    return rows


def _parse_json_bytes(content: bytes, *, limit: int) -> List[Dict[str, Any]]:
    # Handle common UTF-8 BOM prefix written by Windows tools.
    text = content.decode("utf-8-sig", errors="replace")
    data = json.loads(text)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if isinstance(data.get("records"), list):
            items = data.get("records")
        elif isinstance(data.get("items"), list):
            items = data.get("items")
        else:
            # single object
            items = [data]
    else:
        items = []

    out: List[Dict[str, Any]] = []
    for item in items[:limit]:
        if isinstance(item, dict):
            out.append(item)
        else:
            out.append({"value": item})
    return out


def _parse_records(content: bytes, *, name_hint: str, limit: int) -> Tuple[str, List[Dict[str, Any]]]:
    fmt = _detect_format_from_name(name_hint)
    if fmt == "csv":
        return fmt, _parse_csv_bytes(content, limit=limit)
    if fmt == "json":
        return fmt, _parse_json_bytes(content, limit=limit)
    # best-effort: try json then csv
    try:
        return "json", _parse_json_bytes(content, limit=limit)
    except Exception:  # pylint: disable=broad-exception-caught
        try:
            return "csv", _parse_csv_bytes(content, limit=limit)
        except Exception:
            return "unknown", []


def _resolve_local_file_path(connection: Dict[str, Any]) -> Path:
    file_path = (connection.get("file_path") or "").strip()
    if file_path:
        return Path(file_path)
    folder_path = (connection.get("folder_path") or "").strip()
    file_name = (connection.get("file_name") or "").strip()
    if folder_path and file_name:
        return Path(folder_path) / file_name
    return Path("")


@router.get(
    "/{source_id}/sample",
    response_model=SampleRecordsResponse,
    summary="Get sample records for a data source",
    description="Returns a small sample of records from file-based sources for Discovery."
)
async def get_data_source_sample(
    source_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    record = db.get(DataSourceConfigRecord, source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    try:
        connection = decrypt_json(record.connection_ciphertext)
        if not isinstance(connection, dict):
            connection = {}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        # Most common case is Fernet InvalidToken (key mismatch) which stringifies to ''.
        msg = str(e).strip() or (
            "Failed to decrypt data source connection. The encryption key is missing or does not match the key used "
            "when this data source was created. Configure GRAPH_TRACE_CONFIG_ENCRYPTION_KEY (or python_backend/.graphtrace.encryption_key) "
            "and then re-save the data source connection."
        )
        raise HTTPException(status_code=503, detail=msg) from e

    source_type = (record.type or "").lower().strip()
    warnings: List[str] = []
    content: bytes
    name_hint: str = ""

    if source_type in {"file", "local_folder"}:
        path = _resolve_local_file_path(connection)
        if not path or str(path) in ("", "."):
            raise HTTPException(status_code=400, detail="file_path or (folder_path + file_name) is required")
        if not _is_under_allowed_root(path):
            raise HTTPException(status_code=403, detail="Local file path is outside allowed data directories")
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Local file not found")
        name_hint = path.name
        try:
            # Avoid reading huge files into memory
            max_bytes = 512 * 1024
            with open(path, "rb") as fp:
                content = fp.read(max_bytes)
            if path.stat().st_size > max_bytes:
                warnings.append("Sample truncated to 512KB")
        except OSError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    elif source_type in {"aws_s3", "s3"}:
        bucket = (connection.get("bucket") or "").strip()
        key = (connection.get("object_key") or "").strip()
        if not bucket or not key:
            raise HTTPException(status_code=400, detail="bucket and object_key are required")

        try:
            import boto3  # type: ignore

            client_kwargs: Dict[str, Any] = {}
            region = (connection.get("region") or "").strip() or None
            if region:
                client_kwargs["region_name"] = region
            access_key_id = (connection.get("access_key_id") or "").strip() or None
            secret_access_key = (connection.get("secret_access_key") or "").strip() or None
            session_token = (connection.get("session_token") or "").strip() or None
            if access_key_id and secret_access_key:
                client_kwargs["aws_access_key_id"] = access_key_id
                client_kwargs["aws_secret_access_key"] = secret_access_key
            if session_token:
                client_kwargs["aws_session_token"] = session_token

            s3 = boto3.client("s3", **client_kwargs)
            obj = s3.get_object(Bucket=bucket, Key=key)
            body = obj.get("Body")
            if body is None:
                raise HTTPException(status_code=500, detail="S3 object body missing")

            max_bytes = 512 * 1024
            content = body.read(max_bytes)
            name_hint = key

            try:
                content_length = int(obj.get("ContentLength") or 0)
                if content_length and content_length > max_bytes:
                    warnings.append("Sample truncated to 512KB")
            except Exception:
                pass
        except ImportError as e:
            raise HTTPException(status_code=503, detail="boto3 is not installed. Install: pip install boto3") from e
        except HTTPException:
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            raise HTTPException(status_code=500, detail=f"Failed to read S3 object: {str(e)}") from e

    elif source_type in {"azure_blob", "azure"}:
        connection_string = (connection.get("connection_string") or "").strip()
        container_name = (connection.get("container_name") or "").strip()
        blob_name = (connection.get("blob_name") or "").strip()
        if not connection_string or not container_name or not blob_name:
            raise HTTPException(status_code=400, detail="connection_string, container_name, and blob_name are required")

        try:
            from azure.storage.blob import BlobServiceClient  # type: ignore

            service = BlobServiceClient.from_connection_string(connection_string)
            blob_client = service.get_blob_client(container=container_name, blob=blob_name)
            downloader = blob_client.download_blob(max_concurrency=1)
            max_bytes = 512 * 1024
            content = downloader.readall(max_bytes)
            name_hint = blob_name
            try:
                props = blob_client.get_blob_properties()
                size = int(getattr(props, "size", 0) or 0)
                if size and size > max_bytes:
                    warnings.append("Sample truncated to 512KB")
            except Exception:
                pass
        except ImportError as e:
            raise HTTPException(status_code=503, detail="azure-storage-blob is not installed. Install: pip install azure-storage-blob") from e
        except HTTPException:
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            raise HTTPException(status_code=500, detail=f"Failed to read Azure blob: {str(e)}") from e
    else:
        raise HTTPException(status_code=400, detail=f"Sampling is not supported for type '{source_type}'")

    fmt, records = _parse_records(content, name_hint=name_hint, limit=limit)
    if not records:
        warnings.append("No records parsed from sample")

    return SampleRecordsResponse(
        source_id=source_id,
        source_type=source_type,
        count=len(records),
        format=fmt,
        records=records,
        warnings=warnings,
    )

class DataSourceConnection(BaseModel):
    host: Optional[str] = None
    port: Optional[str] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    uri: Optional[str] = None
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    file_path: Optional[str] = None
    folder_path: Optional[str] = None
    file_name: Optional[str] = None

    # AWS S3
    bucket: Optional[str] = None
    object_key: Optional[str] = None
    prefix: Optional[str] = None
    region: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None

    # Azure Blob
    container_name: Optional[str] = None
    blob_name: Optional[str] = None
    blob_prefix: Optional[str] = None
    sas_token: Optional[str] = None
    account_name: Optional[str] = None
    account_key: Optional[str] = None
    connection_string: Optional[str] = None

    @field_serializer(
        "password",
        "api_key",
        "connection_string",
        "secret_access_key",
        "session_token",
        "sas_token",
        "account_key",
        when_used="json",
    )
    def _hide_secrets_in_api(self, value):  # pylint: disable=unused-argument
        return None

class DataSource(BaseModel):
    id: Optional[str] = None
    name: str
    type: str = Field(..., description="Type of data source: database, neo4j, mongodb, api, file, etc.")
    connection: DataSourceConnection
    description: Optional[str] = ""
    status: str = "inactive"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_tested: Optional[str] = None
    test_result: Optional[str] = None

class DataSourceResponse(BaseModel):
    status: str
    message: str
    data: Optional[DataSource] = None

class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict] = None

# In-memory storage for data sources (in production, use a database)
DATA_SOURCES_FILE = "data_sources.json"

def _load_data_sources_legacy_file() -> List[Dict]:
    """Legacy loader for data_sources.json (migration fallback)."""
    try:
        if os.path.exists(DATA_SOURCES_FILE):
            with open(DATA_SOURCES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        return []
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Error loading legacy data sources: %s", e)
        return []

def _allowed_connection_keys() -> set[str]:
    if hasattr(DataSourceConnection, "model_fields"):
        return set(DataSourceConnection.model_fields.keys())
    return set(getattr(DataSourceConnection, "__fields__", {}).keys())


def _filter_connection_fields(connection: Dict[str, Any]) -> Dict[str, Any]:
    allowed = _allowed_connection_keys()
    return {k: v for k, v in (connection or {}).items() if k in allowed}


def _redact_connection(connection: Dict[str, Any]) -> Dict[str, Any]:
    """Return a sanitized copy of connection data."""
    redacted: Dict[str, Any] = {}
    sensitive_exact = {
        "password",
        "secret",
        "token",
        "api_key",
        "access_key",
        "sas",
        "connection_string",
    }
    sensitive_substrings = [
        "password",
        "secret",
        "token",
        "api_key",
        "access_key",
        "connection_string",
        "sas",
    ]
    for k, v in (connection or {}).items():
        key_lower = str(k).lower()
        if key_lower in sensitive_exact or any(s in key_lower for s in sensitive_substrings):
            redacted[k] = None
        else:
            redacted[k] = v
    return redacted


def _merge_connection_secrets(incoming: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve existing secrets when the client sends empty or masked values."""
    merged = dict(incoming or {})
    for secret_key in (
        "password",
        "api_key",
        "connection_string",
        "secret_access_key",
        "session_token",
        "sas_token",
        "account_key",
    ):
        incoming_val = merged.get(secret_key)
        if incoming_val in (None, "", "***"):
            existing_val = (existing or {}).get(secret_key)
            if existing_val:
                merged[secret_key] = existing_val
            else:
                merged.pop(secret_key, None)
    return merged


def _record_to_api(record: DataSourceConfigRecord, connection: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "type": record.type,
        "connection": _redact_connection(_filter_connection_fields(connection)),
        "description": record.description or "",
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "last_tested": record.last_tested.isoformat() if record.last_tested else None,
        "test_result": record.test_result,
    }

@router.get(
    "/",
    response_model=List[DataSource],
    summary="Get All Data Sources",
    description="Retrieve all configured data sources."
)
async def get_data_sources(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Get all data sources (paged)."""
    try:
        total_count = db.query(DataSourceConfigRecord).count()
        response.headers["X-Total-Count"] = str(total_count)

        rows = (
            db.query(DataSourceConfigRecord)
            .order_by(DataSourceConfigRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        if not rows:
            legacy = _load_data_sources_legacy_file()
            # best-effort redaction for legacy payloads
            for item in legacy:
                if isinstance(item, dict) and isinstance(item.get("connection"), dict):
                    item["connection"] = _redact_connection(_filter_connection_fields(item["connection"]))
            response.headers["X-Total-Count"] = str(len(legacy))
            return legacy[skip : skip + limit]

        result: List[Dict[str, Any]] = []
        for row in rows:
            try:
                connection = decrypt_json(row.connection_ciphertext)
                if not isinstance(connection, dict):
                    connection = {}
            except ValueError as e:
                raise HTTPException(status_code=503, detail=str(e)) from e
            except Exception:
                connection = {}
            result.append(_record_to_api(row, connection))
        return result
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        logger.error("Error fetching data sources: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch data sources") from e


@router.get(
    "",
    response_model=List[DataSource],
    summary="Get All Data Sources (No Slash)",
    include_in_schema=False,
)
async def get_data_sources_no_slash(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    # Avoid relying on redirect-slashes behavior when running behind proxies.
    return await get_data_sources(response=response, skip=skip, limit=limit, db=db)

@router.get(
    "/{source_id}",
    response_model=DataSource,
    summary="Get Data Source by ID",
    description="Retrieve a specific data source by its ID."
)
async def get_data_source(source_id: str, db: Session = Depends(get_db)):
    """Get a specific data source by ID"""
    try:
        row = db.get(DataSourceConfigRecord, source_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Data source not found")

        try:
            connection = decrypt_json(row.connection_ciphertext)
            if not isinstance(connection, dict):
                connection = {}
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception:
            connection = {}

        return _record_to_api(row, connection)
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.error("Error fetching data source %s: %s", source_id, e)
        raise HTTPException(status_code=500, detail="Failed to fetch data source") from e

@router.post(
    "/",
    response_model=DataSourceResponse,
    summary="Create Data Source",
    description="Create a new data source configuration."
)
async def create_data_source(source: DataSource, db: Session = Depends(get_db)):
    """Create a new data source"""
    try:
        # Generate ID if not provided
        if not source.id:
            source.id = f"ds_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source.name.strip().replace(' ', '_')[:24]}"
        
        # Reject duplicates by id or name
        existing_by_id = db.get(DataSourceConfigRecord, source.id)
        if existing_by_id is not None:
            raise HTTPException(status_code=400, detail="Data source ID already exists")

        existing_by_name = (
            db.query(DataSourceConfigRecord)
            .filter(DataSourceConfigRecord.name == source.name)
            .first()
        )
        if existing_by_name is not None:
            raise HTTPException(status_code=400, detail="Data source name already exists")

        # Encrypt connection payload
        connection_payload = (
            source.connection.model_dump(mode="python", exclude_none=True)
            if hasattr(source.connection, "model_dump")
            else source.connection.dict(exclude_none=True)
        )

        try:
            ciphertext = encrypt_json(connection_payload)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        record = DataSourceConfigRecord(
            id=source.id,
            name=source.name,
            type=source.type,
            description=source.description,
            status=source.status or "inactive",
            connection_ciphertext=ciphertext,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        
        return DataSourceResponse(
            status="success",
            message="Data source created successfully",
            data=DataSource(**_record_to_api(record, connection_payload))
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.error("Error creating data source: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create data source") from e


@router.post(
    "",
    response_model=DataSourceResponse,
    summary="Create Data Source (No Slash)",
    include_in_schema=False,
)
async def create_data_source_no_slash(source: DataSource, db: Session = Depends(get_db)):
    # Avoid relying on redirect-slashes behavior when running behind proxies.
    return await create_data_source(source=source, db=db)

@router.put(
    "/{source_id}",
    response_model=DataSourceResponse,
    summary="Update Data Source",
    description="Update an existing data source configuration."
)
async def update_data_source(source_id: str, source: DataSource, db: Session = Depends(get_db)):
    """Update an existing data source"""
    try:
        record = db.get(DataSourceConfigRecord, source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Data source not found")

        # Enforce unique name (excluding this record)
        name_conflict = (
            db.query(DataSourceConfigRecord)
            .filter(DataSourceConfigRecord.name == source.name)
            .filter(DataSourceConfigRecord.id != source_id)
            .first()
        )
        if name_conflict is not None:
            raise HTTPException(status_code=400, detail="Data source name already exists")

        incoming_payload = (
            source.connection.model_dump(mode="python", exclude_none=True)
            if hasattr(source.connection, "model_dump")
            else source.connection.dict(exclude_none=True)
        )

        try:
            existing_connection = decrypt_json(record.connection_ciphertext)
            if not isinstance(existing_connection, dict):
                existing_connection = {}
        except Exception:
            existing_connection = {}

        connection_payload = _merge_connection_secrets(incoming_payload, existing_connection)

        record.name = source.name
        record.type = source.type
        record.description = source.description
        record.status = source.status or record.status
        try:
            record.connection_ciphertext = encrypt_json(connection_payload)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        db.commit()
        db.refresh(record)
        
        return DataSourceResponse(
            status="success",
            message="Data source updated successfully",
            data=DataSource(**_record_to_api(record, connection_payload))
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.error("Error updating data source %s: %s", source_id, e)
        raise HTTPException(status_code=500, detail="Failed to update data source") from e

@router.delete(
    "/{source_id}",
    response_model=DataSourceResponse,
    summary="Delete Data Source",
    description="Delete a data source configuration."
)
async def delete_data_source(source_id: str, db: Session = Depends(get_db)):
    """Delete a data source"""
    try:
        record = db.get(DataSourceConfigRecord, source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Data source not found")

        db.delete(record)
        db.commit()
        
        return DataSourceResponse(
            status="success",
            message="Data source deleted successfully"
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        logger.error("Error deleting data source %s: %s", source_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete data source") from e

@router.post(
    "/{source_id}/test",
    response_model=TestConnectionResponse,
    summary="Test Data Source Connection",
    description="Test the connection to a data source."
)
async def test_data_source_connection(source_id: str, db: Session = Depends(get_db)):
    """Test connection to a data source"""
    try:
        logger.info("Testing connection for data source: %s", source_id)
        record = db.get(DataSourceConfigRecord, source_id)
        if record is None:
            logger.error("Data source not found: %s", source_id)
            raise HTTPException(status_code=404, detail="Data source not found")

        try:
            connection = decrypt_json(record.connection_ciphertext)
            if not isinstance(connection, dict):
                connection = {}
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decrypt data source connection: {str(e)}") from e

        source = {
            "id": record.id,
            "name": record.name,
            "type": record.type,
            "connection": connection,
        }

        logger.info("Found data source: %s, type: %s", source.get('name'), source.get('type'))
        
        # Test connection based on source type
        test_result = await _test_connection(source)
        logger.info("Connection test result: %s, message: %s", test_result.success, test_result.message)
        
        # Update source with test results
        record.last_tested = datetime.now()
        record.test_result = "success" if test_result.success else "failed"
        record.status = "active" if test_result.success else "error"
        db.commit()
        
        return test_result
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError, RuntimeError) as e:
        logger.error("Error testing data source %s: %s", source_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to test data source connection: {str(e)}") from e

async def _test_connection(source: Dict) -> TestConnectionResponse:
    """Test connection based on source type"""
    source_type = source.get('type', '').lower()
    connection = source.get('connection', {})
    
    try:
        if source_type == 'neo4j':
            return await _test_neo4j_connection(connection)
        elif source_type == 'database':
            return await _test_database_connection(connection)
        elif source_type == 'postgres':
            return await _test_postgres_connection(connection)
        elif source_type == 'mongodb':
            return await _test_mongodb_connection(connection)
        elif source_type == 'api':
            return await _test_api_connection(connection)
        elif source_type == 'file':
            return await _test_file_connection(connection)
        elif source_type == 'local_folder':
            return await _test_local_folder_connection(connection)
        elif source_type in {'aws_s3', 's3'}:
            return await _test_s3_connection(connection)
        elif source_type in {'azure_blob', 'azure'}:
            return await _test_azure_blob_connection(connection)
        else:
            return TestConnectionResponse(
                success=False,
                message=f"Unsupported data source type: {source_type}"
            )
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, neo4j.exceptions.Neo4jError) as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection test failed: {str(e)}"
        )

async def _test_neo4j_connection(connection: Dict) -> TestConnectionResponse:
    """Test Neo4j connection"""
    try:
        uri = connection.get('uri') or f"neo4j://{connection.get('host', 'localhost')}:{connection.get('port', '7687')}"
        username = connection.get('username', 'neo4j')
        password = connection.get('password', '')
        database = connection.get('database', 'neo4j')
        
        driver = neo4j.AsyncGraphDatabase.driver(uri, auth=(username, password))
        
        async with driver.session(database=database) as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
        
        await driver.close()
        
        return TestConnectionResponse(
            success=True,
            message="Neo4j connection successful",
            details={"database": database, "uri": uri}
        )
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, neo4j.exceptions.Neo4jError) as e:
        return TestConnectionResponse(
            success=False,
            message=f"Neo4j connection failed: {str(e)}"
        )

async def _test_database_connection(connection: Dict) -> TestConnectionResponse:
    """Test SQL database connection (basic validation)"""
    try:
        # Basic validation of required fields
        required_fields = ['host', 'database', 'username']
        missing_fields = [field for field in required_fields if not connection.get(field)]
        
        if missing_fields:
            return TestConnectionResponse(
                success=False,
                message=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # In a real implementation, you would test the actual database connection
        # For now, we'll just validate the configuration
        return TestConnectionResponse(
            success=True,
            message="Database configuration validated (connection test would require database driver)",
            details={"host": connection.get('host'), "database": connection.get('database')}
        )
    except (ValueError, TypeError, KeyError) as e:
        return TestConnectionResponse(
            success=False,
            message=f"Database validation failed: {str(e)}"
        )

async def _test_postgres_connection(connection: Dict) -> TestConnectionResponse:
    """Test PostgreSQL connection using psycopg (v3)"""
    try:
        import psycopg
        
        host = connection.get('host', 'localhost')
        port = connection.get('port', '5432')
        database = connection.get('database', 'postgres')
        username = connection.get('username', 'postgres')
        password = connection.get('password', '')
        
        conninfo = f"host={host} port={port} dbname={database} user={username} password={password} connect_timeout=5"
        
        with psycopg.connect(conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
        
        return TestConnectionResponse(
            success=True,
            message="PostgreSQL connection successful",
            details={"host": host, "port": port, "database": database, "version": version[:80]}
        )
    except ImportError:
        return TestConnectionResponse(
            success=False,
            message="psycopg driver not installed"
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"PostgreSQL connection failed: {str(e)}"
        )

async def _test_mongodb_connection(connection: Dict) -> TestConnectionResponse:
    """Test MongoDB connection"""
    try:
        required_fields = ['host', 'database']
        missing_fields = [field for field in required_fields if not connection.get(field)]
        
        if missing_fields:
            return TestConnectionResponse(
                success=False,
                message=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        host = connection.get('host', 'localhost')
        port = connection.get('port', 27017)
        database = connection.get('database')
        username = connection.get('username')
        password = connection.get('password')
        
        # Build MongoDB URI
        if username and password:
            from urllib.parse import quote_plus
            uri = f"mongodb://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}"
        else:
            uri = f"mongodb://{host}:{port}/{database}"
        
        # Test connection using pymongo
        try:
            from pymongo import MongoClient
            
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # Force a connection attempt
            client.admin.command('ping')
            client.close()
            
            return TestConnectionResponse(
                success=True,
                message="MongoDB connection successful",
                details={"host": host, "database": database}
            )
        except ImportError:
            # pymongo not installed - try basic TCP test
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                sock.connect((host, int(port)))
                sock.close()
                return TestConnectionResponse(
                    success=True,
                    message="MongoDB server is reachable (pymongo not installed for full test)",
                    details={"host": host, "port": port}
                )
            except (socket.error, socket.timeout) as sock_err:
                return TestConnectionResponse(
                    success=False,
                    message=f"Cannot reach MongoDB server: {str(sock_err)}"
                )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"MongoDB connection failed: {str(e)}"
        )

async def _test_api_connection(connection: Dict) -> TestConnectionResponse:
    """Test API connection with actual HTTP request"""
    try:
        endpoint = connection.get('endpoint')
        if not endpoint:
            return TestConnectionResponse(
                success=False,
                message="API endpoint is required"
            )
        
        # Get optional auth configuration
        auth_type = connection.get('auth_type', 'none')
        headers = connection.get('headers', {})
        timeout = connection.get('timeout', 10)
        
        import httpx
        
        # Build headers with authentication if provided
        request_headers = dict(headers)
        
        if auth_type == 'bearer':
            token = connection.get('token') or connection.get('api_key')
            if token:
                request_headers['Authorization'] = f'Bearer {token}'
        elif auth_type == 'api_key':
            api_key = connection.get('api_key')
            api_key_header = connection.get('api_key_header', 'X-API-Key')
            if api_key:
                request_headers[api_key_header] = api_key
        elif auth_type == 'basic':
            username = connection.get('username', '')
            password = connection.get('password', '')
            import base64
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            request_headers['Authorization'] = f'Basic {credentials}'
        
        # Make HEAD request to test connectivity (lighter than GET)
        async with httpx.AsyncClient(timeout=timeout, verify=connection.get('verify_ssl', True)) as client:
            try:
                response = await client.head(endpoint, headers=request_headers, follow_redirects=True)
            except httpx.HTTPStatusError:
                # HEAD not allowed, try GET
                response = await client.get(endpoint, headers=request_headers, follow_redirects=True)
        
        if response.status_code < 400:
            return TestConnectionResponse(
                success=True,
                message=f"API connection successful (HTTP {response.status_code})",
                details={"endpoint": endpoint, "status_code": response.status_code}
            )
        else:
            return TestConnectionResponse(
                success=False,
                message=f"API returned error status: HTTP {response.status_code}",
                details={"endpoint": endpoint, "status_code": response.status_code}
            )
            
    except ImportError:
        return TestConnectionResponse(
            success=False,
            message="httpx library not installed for API testing. Run: pip install httpx"
        )
    except httpx.ConnectError as e:
        return TestConnectionResponse(
            success=False,
            message=f"Cannot connect to API endpoint: {str(e)}"
        )
    except httpx.TimeoutException:
        return TestConnectionResponse(
            success=False,
            message=f"API connection timed out after {timeout} seconds"
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"API connection failed: {str(e)}"
        )

async def _test_file_connection(connection: Dict) -> TestConnectionResponse:
    """Test file connection"""
    try:
        file_path = connection.get('file_path')
        if not file_path:
            return TestConnectionResponse(
                success=False,
                message="File path is required"
            )
        
        if os.path.exists(file_path):
            return TestConnectionResponse(
                success=True,
                message="File exists and is accessible",
                details={"file_path": file_path, "size": os.path.getsize(file_path)}
            )
        else:
            return TestConnectionResponse(
                success=False,
                message="File not found or not accessible"
            )
    except (ValueError, TypeError, KeyError, OSError) as e:
        return TestConnectionResponse(
            success=False,
            message=f"File validation failed: {str(e)}"
        )


async def _test_local_folder_connection(connection: Dict) -> TestConnectionResponse:
    """Test local folder connection."""
    try:
        folder_path = (connection.get("folder_path") or "").strip()
        if not folder_path:
            return TestConnectionResponse(success=False, message="Folder path is required")

        folder = Path(folder_path)
        if folder.exists() and folder.is_dir():
            try:
                children = list(folder.iterdir())
            except OSError:
                children = []
            return TestConnectionResponse(
                success=True,
                message="Folder exists and is accessible",
                details={"folder_path": str(folder), "items": len(children)},
            )

        return TestConnectionResponse(success=False, message="Folder not found or not accessible")
    except (ValueError, TypeError, KeyError, OSError) as e:
        return TestConnectionResponse(success=False, message=f"Folder validation failed: {str(e)}")


async def _test_s3_connection(connection: Dict) -> TestConnectionResponse:
    """Test AWS S3 connection (best effort)."""
    bucket = (connection.get("bucket") or "").strip()
    region = (connection.get("region") or "").strip() or None
    access_key_id = (connection.get("access_key_id") or "").strip() or None
    secret_access_key = (connection.get("secret_access_key") or "").strip() or None
    session_token = (connection.get("session_token") or "").strip() or None
    if not bucket:
        return TestConnectionResponse(success=False, message="bucket is required")

    try:
        import boto3  # type: ignore
        from botocore.exceptions import BotoCoreError, ClientError  # type: ignore

        client_kwargs: Dict[str, Any] = {}
        if region:
            client_kwargs["region_name"] = region
        if access_key_id and secret_access_key:
            client_kwargs["aws_access_key_id"] = access_key_id
            client_kwargs["aws_secret_access_key"] = secret_access_key
        if session_token:
            client_kwargs["aws_session_token"] = session_token

        s3 = boto3.client("s3", **client_kwargs)
        # Lightweight check
        s3.head_bucket(Bucket=bucket)
        return TestConnectionResponse(
            success=True,
            message="S3 bucket is accessible",
            details={"bucket": bucket, "region": region},
        )
    except ImportError:
        return TestConnectionResponse(
            success=False,
            message="boto3 is not installed for S3 connectivity. Install: pip install boto3",
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Avoid importing botocore types in the except signature if missing
        return TestConnectionResponse(success=False, message=f"S3 connection failed: {str(e)}")


async def _test_azure_blob_connection(connection: Dict) -> TestConnectionResponse:
    """Test Azure Blob Storage connection (best effort)."""
    connection_string = (connection.get("connection_string") or "").strip()
    container_name = (connection.get("container_name") or "").strip() or None
    if not connection_string:
        return TestConnectionResponse(success=False, message="connection_string is required")

    try:
        from azure.storage.blob import BlobServiceClient  # type: ignore

        service = BlobServiceClient.from_connection_string(connection_string)
        if container_name:
            container = service.get_container_client(container_name)
            # list at most one blob
            _ = next(container.list_blobs(results_per_page=1), None)
        return TestConnectionResponse(
            success=True,
            message="Azure Blob Storage is accessible",
            details={"container_name": container_name},
        )
    except ImportError:
        return TestConnectionResponse(
            success=False,
            message="azure-storage-blob is not installed. Install: pip install azure-storage-blob",
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        return TestConnectionResponse(success=False, message=f"Azure Blob connection failed: {str(e)}")

@router.get(
    "/types/supported",
    summary="Get Supported Data Source Types",
    description="Get list of supported data source types and their configuration requirements."
)
async def get_supported_types():
    """Get supported data source types"""
    return {
        "database": {
            "name": "SQL Database",
            "fields": ["host", "port", "database", "username", "password"],
            "default_port": "5433",
            "description": "PostgreSQL, MySQL, SQL Server, etc."
        },
        "neo4j": {
            "name": "Neo4j Graph Database",
            "fields": ["uri", "username", "password", "database"],
            "default_port": "7687",
            "description": "Neo4j graph database"
        },
        "mongodb": {
            "name": "MongoDB",
            "fields": ["host", "port", "database", "username", "password"],
            "default_port": "27017",
            "description": "MongoDB document database"
        },
        "api": {
            "name": "REST API",
            "fields": ["endpoint", "api_key"],
            "description": "REST API endpoint"
        },
        "file": {
            "name": "File System",
            "fields": ["file_path"],
            "description": "CSV, JSON, XML, Excel files"
        },
        "local_folder": {
            "name": "Local Folder",
            "fields": ["folder_path", "file_name"],
            "description": "Read files from a local folder path"
        },
        "aws_s3": {
            "name": "AWS S3",
            "fields": ["bucket", "object_key", "region", "access_key_id", "secret_access_key", "session_token"],
            "description": "Read files from an S3 bucket"
        },
        "azure_blob": {
            "name": "Azure Blob Storage",
            "fields": ["connection_string", "container_name", "blob_name"],
            "description": "Read files from Azure Blob Storage"
        }
    }
