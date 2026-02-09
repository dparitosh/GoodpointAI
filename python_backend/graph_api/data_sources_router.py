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
from models.admin_config_models import ConnectionConfig

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
    # python_backend/graph_api -> python_backend -> repo root
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
    # Allow all local paths for desktop app usage
    return True


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


# ---------------------------------------------------------------------------
# System connection sampling (admin-registered connections)
# ---------------------------------------------------------------------------

_DATABASE_TYPES = {"postgres", "postgresql", "database", "mysql", "sqlserver", "mssql", "oracle"}
_NEO4J_TYPES = {"neo4j"}
_API_TYPES = {"rest_api", "odata", "graphql", "api"}
_PLM_TYPES = {"teamcenter", "3dexperience", "windchill", "aras", "codebeamer", "enovia"}
_FILE_STORAGE_TYPES = {"s3", "aws_s3", "azure_blob", "azure", "local_folder", "onedrive", "google_drive", "file"}


async def _sample_system_connection(
    source_id: str,
    conn_type: str,
    conn_dict: Dict[str, Any],
    limit: int,
) -> SampleRecordsResponse:
    """Return sample records from an admin-registered system connection.

    Dispatches to the appropriate sampling strategy based on *conn_type*.
    Returns a ``SampleRecordsResponse`` with the sampled records (may be
    empty if the underlying system is unreachable or the type is not yet
    supported for live sampling).
    """
    warnings: List[str] = []
    records: List[Dict[str, Any]] = []
    fmt = "json"

    try:
        if conn_type in _DATABASE_TYPES:
            records, warnings = await _sample_postgres(conn_dict, limit)
        elif conn_type in _NEO4J_TYPES:
            records, warnings = await _sample_neo4j(conn_dict, limit)
        elif conn_type in _API_TYPES:
            records, warnings, fmt = await _sample_api_endpoint(conn_dict, conn_type, limit)
        elif conn_type in _PLM_TYPES:
            records, warnings, fmt = await _sample_plm_system(conn_dict, conn_type, limit)
        elif conn_type in _FILE_STORAGE_TYPES:
            records, warnings, fmt = _sample_file_storage(conn_dict, conn_type, limit)
        else:
            warnings.append(
                f"Live sampling is not yet supported for connection type '{conn_type}'. "
                "Discovery will use synthetic sample data."
            )
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Sampling failed for %s (%s): %s", source_id, conn_type, exc, exc_info=True)
        warnings.append(f"Sampling failed: {str(exc)}")

    return SampleRecordsResponse(
        source_id=source_id,
        source_type=conn_type,
        count=len(records),
        format=fmt,
        records=records,
        warnings=warnings,
    )


async def _sample_postgres(conn: Dict[str, Any], limit: int) -> tuple:
    """Sample rows from a PostgreSQL / SQL database connection."""
    warnings: List[str] = []
    records: List[Dict[str, Any]] = []

    try:
        import psycopg  # type: ignore
    except ImportError:
        warnings.append("psycopg driver not installed — cannot sample SQL database")
        return records, warnings

    host = conn.get("host", "localhost")
    port = conn.get("port", "5432")
    database = conn.get("database", "postgres")
    username = conn.get("username", "postgres")
    password = conn.get("password", "")

    conninfo = (
        f"host={host} port={port} dbname={database} "
        f"user={username} password={password} connect_timeout=10"
    )

    try:
        with psycopg.connect(conninfo) as db_conn:
            with db_conn.cursor() as cur:
                # Discover the first user table to sample
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                    "ORDER BY table_name LIMIT 1"
                )
                row = cur.fetchone()
                if not row:
                    warnings.append("No public tables found in database")
                    return records, warnings

                table_name = row[0]
                # Use quoted identifier to avoid SQL injection
                cur.execute(
                    f'SELECT * FROM "{table_name}" LIMIT %s',  # noqa: S608
                    (limit,),
                )
                columns = [desc[0] for desc in cur.description]
                for db_row in cur.fetchall():
                    records.append(dict(zip(columns, db_row)))

                warnings.append(f"Sampled from table: {table_name}")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        warnings.append(f"SQL sampling error: {str(exc)}")

    return records, warnings


async def _sample_neo4j(conn: Dict[str, Any], limit: int) -> tuple:
    """Sample nodes from a Neo4j database."""
    warnings: List[str] = []
    records: List[Dict[str, Any]] = []

    uri = conn.get("uri") or conn.get("connection_string") or (
        f"neo4j://{conn.get('host', 'localhost')}:{conn.get('port', '7687')}"
    )
    username = conn.get("username", "neo4j")
    password = conn.get("password", "")
    database = conn.get("database", "neo4j")

    try:
        driver = neo4j.AsyncGraphDatabase.driver(uri, auth=(username, password))
        try:
            async with driver.session(database=database) as session:
                result = await session.run(
                    "MATCH (n) RETURN properties(n) AS props LIMIT $lim",
                    lim=limit,
                )
                async for record in result:
                    props = record["props"]
                    if isinstance(props, dict):
                        records.append(props)
        finally:
            await driver.close()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        warnings.append(f"Neo4j sampling error: {str(exc)}")

    return records, warnings


async def _sample_api_endpoint(
    conn: Dict[str, Any], api_type: str, limit: int
) -> tuple:
    """Sample records from a REST / OData / GraphQL endpoint."""
    import httpx  # noqa: E402

    warnings: List[str] = []
    records: List[Dict[str, Any]] = []
    fmt = "json"

    extra = conn.get("extra_options") or {}
    endpoint_url = (extra.get("endpoint_url") or conn.get("endpoint") or "").strip()
    if not endpoint_url:
        warnings.append("endpoint_url is required for API sampling")
        return records, warnings, fmt

    auth_method = (extra.get("auth_method") or "none").lower()
    headers: Dict[str, str] = {"Accept": "application/json"}

    # Custom headers
    try:
        custom_hdr = extra.get("custom_headers")
        if custom_hdr and isinstance(custom_hdr, str):
            headers.update(json.loads(custom_hdr))
    except Exception:
        pass

    auth = None
    if auth_method == "basic":
        auth = httpx.BasicAuth(conn.get("username", ""), conn.get("password", ""))
    elif auth_method in ("bearer", "api_key"):
        token = conn.get("password", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    # OData: append $top; GraphQL: just GET the endpoint
    url = endpoint_url
    if api_type == "odata" and "$top" not in url.lower():
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}$top={limit}"

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            if api_type == "graphql":
                # For GraphQL, POST an introspection-like query for first N records.
                # Without knowing the schema we send a generic query; the user may
                # need to configure the object_types/query in extra_options.
                graphql_query = extra.get("query") or '{ __schema { types { name } } }'
                resp = await client.post(
                    url,
                    json={"query": graphql_query},
                    headers=headers,
                    auth=auth,
                )
            else:
                resp = await client.get(url, headers=headers, auth=auth)

        if resp.status_code >= 400:
            warnings.append(f"API returned HTTP {resp.status_code}")
            return records, warnings, fmt

        body = resp.json()

        # Normalise response: many APIs wrap results in value/data/results/items
        if isinstance(body, list):
            records = body[:limit]
        elif isinstance(body, dict):
            for key in ("value", "data", "results", "items", "records", "d"):
                candidate = body.get(key)
                if isinstance(candidate, list):
                    records = candidate[:limit]
                    break
            if not records:
                # GraphQL nested: data -> <typename> -> [...]
                data = body.get("data")
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list):
                            records = v[:limit]
                            break
            if not records:
                # Return the single object as a one-record result
                records = [body]
    except Exception as exc:  # pylint: disable=broad-exception-caught
        warnings.append(f"API sampling error: {str(exc)}")

    return records, warnings, fmt


async def _sample_plm_system(
    conn: Dict[str, Any], plm_type: str, limit: int
) -> tuple:
    """Sample records from a PLM system (Teamcenter, Windchill, etc.)."""
    import httpx  # noqa: E402

    warnings: List[str] = []
    records: List[Dict[str, Any]] = []
    fmt = "json"

    extra = conn.get("extra_options") or {}
    server_url = (extra.get("server_url") or "").strip()
    if not server_url:
        warnings.append("server_url is required for PLM sampling")
        return records, warnings, fmt

    username = conn.get("username", "")
    password = conn.get("password", "")
    auth_method = (extra.get("auth_method") or "basic").lower()
    api_version = extra.get("api_version", "")
    object_types = extra.get("object_types", "")

    auth = None
    headers: Dict[str, str] = {"Accept": "application/json"}

    if auth_method == "basic" and username:
        auth = httpx.BasicAuth(username, password)
    elif auth_method == "bearer" and password:
        headers["Authorization"] = f"Bearer {password}"

    # Build a type-specific sample endpoint.
    # These are best-effort defaults; actual PLM APIs vary by version/config.
    search_path = ""
    if plm_type == "teamcenter":
        obj_type = object_types or "Item"
        search_path = f"/internal/aws2/query?searchString=*&maxToReturn={limit}&typeOfSearch=QUICK_SEARCH&typesToInclude={obj_type}"
        if api_version:
            search_path = f"/tc/{api_version}{search_path}"
    elif plm_type == "windchill":
        obj_type = object_types or "wt.part.WTPart"
        search_path = f"/Windchill/servlet/odata/v6/ProdMgmt/Parts?$top={limit}"
    elif plm_type == "3dexperience":
        search_path = f"/resources/v1/modeler/dseng/dseng:EngItem/search?$top={limit}"
    elif plm_type == "aras":
        obj_type = object_types or "Part"
        search_path = f"/server/odata/{obj_type}?$top={limit}"
    elif plm_type == "codebeamer":
        search_path = f"/api/v3/items/query?page=1&pageSize={limit}"
    elif plm_type == "enovia":
        search_path = f"/resources/v1/modeler/dseng/dseng:EngItem/search?$top={limit}"

    url = server_url.rstrip("/") + search_path

    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            resp = await client.get(url, headers=headers, auth=auth)

        if resp.status_code >= 400:
            warnings.append(f"PLM API returned HTTP {resp.status_code}")
            return records, warnings, fmt

        body = resp.json()

        # Normalise: PLM APIs wrap items in various keys
        if isinstance(body, list):
            records = body[:limit]
        elif isinstance(body, dict):
            for key in ("member", "objects", "data", "value", "results",
                        "items", "searchResults", "modelObjects"):
                candidate = body.get(key)
                if isinstance(candidate, list):
                    records = candidate[:limit]
                    break
            if not records:
                records = [body]

        warnings.append(f"Sampled {len(records)} records from {plm_type} ({url})")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        warnings.append(f"PLM sampling error ({plm_type}): {str(exc)}")

    return records, warnings, fmt


def _sample_file_storage(
    conn: Dict[str, Any], conn_type: str, limit: int
) -> tuple:
    """Sample records from file-based storage connections (S3, Azure Blob, local folder)."""
    warnings: List[str] = []
    records: List[Dict[str, Any]] = []
    fmt = "unknown"

    extra = conn.get("extra_options") or {}

    if conn_type in ("local_folder",):
        folder = (extra.get("folder_path") or conn.get("host") or "").strip()
        if not folder:
            warnings.append("folder_path is required for local folder sampling")
            return records, warnings, fmt
        folder_path = Path(folder)
        if not _is_under_allowed_root(folder_path):
            warnings.append("Local folder path is outside allowed data directories")
            return records, warnings, fmt
        # Find the first parseable file
        for ext in ("*.csv", "*.json", "*.xml"):
            files = sorted(folder_path.glob(ext))
            if files:
                target = files[0]
                try:
                    content = target.read_bytes()[:512 * 1024]
                    fmt, records = _parse_records(content, name_hint=target.name, limit=limit)
                    warnings.append(f"Sampled from: {target.name}")
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    warnings.append(f"Error reading {target.name}: {str(exc)}")
                break
        if not records:
            warnings.append("No parseable files found in folder")

    elif conn_type in ("s3", "aws_s3"):
        try:
            import boto3  # type: ignore
        except ImportError:
            warnings.append("boto3 not installed — cannot sample S3")
            return records, warnings, fmt

        bucket = (extra.get("bucket") or "").strip()
        key = (extra.get("object_key") or "").strip()
        if not bucket:
            warnings.append("bucket is required for S3 sampling")
            return records, warnings, fmt
        if not key:
            # List first object and sample it
            try:
                s3_kw: Dict[str, Any] = {}
                region = (extra.get("region") or "").strip()
                if region:
                    s3_kw["region_name"] = region
                ak = (extra.get("access_key_id") or "").strip()
                sk = (extra.get("secret_access_key") or "").strip()
                if ak and sk:
                    s3_kw["aws_access_key_id"] = ak
                    s3_kw["aws_secret_access_key"] = sk
                s3 = boto3.client("s3", **s3_kw)
                listing = s3.list_objects_v2(Bucket=bucket, MaxKeys=5)
                contents = listing.get("Contents", [])
                for obj_meta in contents:
                    candidate_key = obj_meta.get("Key", "")
                    if candidate_key.lower().endswith((".csv", ".json")):
                        key = candidate_key
                        break
                if not key and contents:
                    key = contents[0].get("Key", "")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                warnings.append(f"S3 listing error: {str(exc)}")
                return records, warnings, fmt

        if key:
            try:
                s3_kw2: Dict[str, Any] = {}
                region = (extra.get("region") or "").strip()
                if region:
                    s3_kw2["region_name"] = region
                ak = (extra.get("access_key_id") or "").strip()
                sk = (extra.get("secret_access_key") or "").strip()
                if ak and sk:
                    s3_kw2["aws_access_key_id"] = ak
                    s3_kw2["aws_secret_access_key"] = sk
                s3 = boto3.client("s3", **s3_kw2)
                obj = s3.get_object(Bucket=bucket, Key=key)
                content = obj["Body"].read(512 * 1024)
                fmt, records = _parse_records(content, name_hint=key, limit=limit)
                warnings.append(f"Sampled from s3://{bucket}/{key}")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                warnings.append(f"S3 read error: {str(exc)}")

    elif conn_type in ("azure_blob", "azure"):
        cs = (conn.get("connection_string") or "").strip()
        container = (extra.get("container_name") or "").strip()
        blob = (extra.get("blob_name") or "").strip()
        if not cs or not container:
            warnings.append("connection_string and container_name are required for Azure Blob sampling")
            return records, warnings, fmt
        try:
            from azure.storage.blob import BlobServiceClient  # type: ignore
        except ImportError:
            warnings.append("azure-storage-blob not installed")
            return records, warnings, fmt

        try:
            service = BlobServiceClient.from_connection_string(cs)
            if not blob:
                container_client = service.get_container_client(container)
                for b in container_client.list_blobs(results_per_page=5):
                    if b.name.lower().endswith((".csv", ".json")):
                        blob = b.name
                        break
                if not blob:
                    warnings.append("No parseable blobs found in container")
                    return records, warnings, fmt

            blob_client = service.get_blob_client(container=container, blob=blob)
            content = blob_client.download_blob().readall()[:512 * 1024]
            fmt, records = _parse_records(content, name_hint=blob, limit=limit)
            warnings.append(f"Sampled from {container}/{blob}")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            warnings.append(f"Azure Blob sampling error: {str(exc)}")

    else:
        warnings.append(f"File storage sampling not implemented for: {conn_type}")

    return records, warnings, fmt


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
    # Handle System Connections (registered via Admin Configuration Center)
    if source_id.startswith("conn_"):
        conn_id = source_id[5:]
        conn = db.get(ConnectionConfig, conn_id)
        if conn is None:
            raise HTTPException(status_code=404, detail="System connection not found")

        conn_type = (conn.connection_type or "").lower().strip()
        extra = conn.extra_options if isinstance(conn.extra_options, dict) else {}

        # Build a unified connection dict that downstream helpers can consume
        conn_dict: Dict[str, Any] = {
            "host": conn.host,
            "port": conn.port,
            "database": conn.database,
            "username": conn.username,
            "password": conn.password,
            "connection_string": conn.connection_string,
            "extra_options": extra,
            # Also flatten common extra fields for backward compatibility
            **{k: v for k, v in extra.items() if isinstance(v, str)},
        }

        return await _sample_system_connection(source_id, conn_type, conn_dict, limit)

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
    type: str = Field(..., description="Type of data source: database, neo4j, api, file, etc.")
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
    """Get all data sources (paged). Includes System Connections from Admin Config."""
    try:
        # 1. Fetch System Connections
        conn_query = db.query(ConnectionConfig).filter(ConnectionConfig.status != "deleted")
        conn_count = conn_query.count()
        
        # 2. Fetch Data Sources
        ds_query = db.query(DataSourceConfigRecord)
        ds_count = ds_query.count()
        
        response.headers["X-Total-Count"] = str(conn_count + ds_count)
        
        result: List[Dict[str, Any]] = []

        # -- Process Connections (if page includes them) --
        slots_remaining = limit
        
        if skip < conn_count:
            # We need to fetch some connections
            # Since we can't offset/limit easily across tables, we fetch all connections 
            # (assuming count is low < 100) and slice in memory.
            all_conns = conn_query.order_by(ConnectionConfig.name).all()
            
            # Slice for current page
            conns_to_show = all_conns[skip : skip + limit]
            
            for c in conns_to_show:
                result.append({
                    "id": f"conn_{c.id}", # Prefix to distinguish from data source UUIDs
                    "name": c.name,
                    "type": c.connection_type,
                    "connection": {
                        "host": c.host,
                        "port": c.port,
                        "database": c.database,
                        "username": c.username,
                        "connection_string_preview": "***" if c.password else None
                    },
                    "description": c.description or f"System {c.connection_type} connection",
                    "status": c.status,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                    "last_tested": c.last_health_check.isoformat() if c.last_health_check else None,
                    "test_result": c.health_status or "unknown"
                })
            
            slots_remaining -= len(conns_to_show)

        # -- Process Data Sources --
        if slots_remaining > 0:
            # Calculate offset for DataSources
            # If we started after connections, offset is (skip - conn_count)
            # If we started inside connections, offset is 0, we just take remaining slots
            ds_skip = max(0, skip - conn_count)
            
            rows = (
                ds_query
                .order_by(DataSourceConfigRecord.created_at.desc())
                .offset(ds_skip)
                .limit(slots_remaining)
                .all()
            )

            # Fallback for empty DB (legacy checks)
            if not rows and conn_count == 0 and ds_count == 0:
                 legacy = _load_data_sources_legacy_file()
                 # best-effort redaction for legacy payloads
                 for item in legacy:
                     if isinstance(item, dict) and isinstance(item.get("connection"), dict):
                         item["connection"] = _redact_connection(_filter_connection_fields(item["connection"]))
                 response.headers["X-Total-Count"] = str(len(legacy))
                 return legacy[skip : skip + limit]

            for row in rows:
                try:
                    connection = decrypt_json(row.connection_ciphertext)
                    if not isinstance(connection, dict):
                        connection = {}
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

        # Handle System Connections
        if source_id.startswith("conn_"):
            conn_id = source_id[5:]
            conn = db.get(ConnectionConfig, conn_id)
            if conn is None:
                raise HTTPException(status_code=404, detail="System connection not found")
            
            source = {
                "id": source_id,
                "name": conn.name,
                "type": conn.connection_type,
                "connection": {
                    "host": conn.host,
                    "port": conn.port,
                    "database": conn.database,
                    "username": conn.username,
                    "password": conn.password,
                    "uri": conn.connection_string
                }
            }
        else:
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
        
        # Update source with test results (Only for DataSources, not Connections)
        # Check if we have a 'record' object from DataSourceConfigRecord
        if 'record' in locals() and record:
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
        elif source_type in {'rest_api', 'odata', 'graphql'}:
            return await _test_api_endpoint_connection(connection, source_type)
        elif source_type in {'teamcenter', '3dexperience', 'windchill', 'aras', 'codebeamer', 'enovia'}:
            return await _test_plm_connection(connection, source_type)
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


async def _test_api_endpoint_connection(connection: Dict, api_type: str = "rest_api") -> TestConnectionResponse:
    """Test REST / OData / GraphQL endpoint reachability."""
    import httpx  # noqa: E402 — available in requirements.txt

    extra = connection.get("extra_options") or {}
    endpoint_url = (extra.get("endpoint_url") or connection.get("endpoint") or "").strip()
    if not endpoint_url:
        return TestConnectionResponse(success=False, message="endpoint_url is required")

    auth_method = (extra.get("auth_method") or "none").lower()
    headers: Dict[str, str] = {"Accept": "application/json"}

    # Inject custom headers if provided
    try:
        custom = extra.get("custom_headers")
        if custom and isinstance(custom, str):
            import json as _json
            headers.update(_json.loads(custom))
    except Exception:
        pass

    # Auth
    auth = None
    if auth_method == "basic":
        username = connection.get("username", "")
        password = connection.get("password", "")
        auth = httpx.BasicAuth(username, password)
    elif auth_method in ("bearer", "api_key"):
        token = connection.get("password", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(endpoint_url, headers=headers, auth=auth)
        if resp.status_code < 400:
            return TestConnectionResponse(
                success=True,
                message=f"{api_type.upper()} endpoint reachable (HTTP {resp.status_code})",
                details={"url": endpoint_url, "status": resp.status_code},
            )
        return TestConnectionResponse(
            success=False,
            message=f"Endpoint returned HTTP {resp.status_code}",
            details={"url": endpoint_url, "status": resp.status_code},
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        return TestConnectionResponse(success=False, message=f"Cannot reach {api_type} endpoint: {str(e)}")


async def _test_plm_connection(connection: Dict, plm_type: str) -> TestConnectionResponse:
    """Test PLM system connection by probing the server URL."""
    import httpx  # noqa: E402

    extra = connection.get("extra_options") or {}
    server_url = (extra.get("server_url") or "").strip()
    if not server_url:
        return TestConnectionResponse(success=False, message="server_url is required")

    plm_labels = {
        "teamcenter": "Siemens Teamcenter",
        "3dexperience": "Dassault 3DEXPERIENCE",
        "windchill": "PTC Windchill",
        "aras": "Aras Innovator",
        "codebeamer": "Codebeamer",
        "enovia": "ENOVIA",
    }
    label = plm_labels.get(plm_type, plm_type)

    username = connection.get("username", "")
    password = connection.get("password", "")
    auth_method = (extra.get("auth_method") or "basic").lower()
    auth = None
    headers: Dict[str, str] = {"Accept": "application/json"}

    if auth_method == "basic" and username:
        auth = httpx.BasicAuth(username, password)
    elif auth_method == "bearer" and password:
        headers["Authorization"] = f"Bearer {password}"

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(server_url, headers=headers, auth=auth)
        if resp.status_code < 400:
            return TestConnectionResponse(
                success=True,
                message=f"{label} server is reachable (HTTP {resp.status_code})",
                details={"url": server_url, "plm": plm_type, "status": resp.status_code},
            )
        return TestConnectionResponse(
            success=False,
            message=f"{label} responded with HTTP {resp.status_code}",
            details={"url": server_url, "status": resp.status_code},
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        return TestConnectionResponse(success=False, message=f"Cannot reach {label}: {str(e)}")


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
        "api": {
            "name": "REST API",
            "fields": ["endpoint", "api_key"],
            "description": "REST API endpoint"
        },
        "rest_api": {
            "name": "REST API",
            "fields": ["endpoint_url", "auth_method", "username", "password", "custom_headers"],
            "description": "Generic REST API endpoint with flexible auth"
        },
        "odata": {
            "name": "OData API",
            "fields": ["endpoint_url", "odata_version", "auth_method", "username", "password"],
            "description": "OData V2/V4 service endpoint (SAP, Dynamics, etc.)"
        },
        "graphql": {
            "name": "GraphQL API",
            "fields": ["endpoint_url", "auth_method", "username", "password"],
            "description": "GraphQL API endpoint"
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
        },
        "teamcenter": {
            "name": "Siemens Teamcenter",
            "fields": ["server_url", "username", "password", "security_context", "api_version"],
            "description": "Siemens Teamcenter PLM via SOA/REST gateway"
        },
        "3dexperience": {
            "name": "Dassault 3DEXPERIENCE",
            "fields": ["server_url", "username", "password", "security_context", "tenant"],
            "description": "Dassault 3DEXPERIENCE platform (3DSpace, ENOVIA)"
        },
        "windchill": {
            "name": "PTC Windchill",
            "fields": ["server_url", "username", "password", "api_version"],
            "description": "PTC Windchill PLM via OData/REST API"
        },
        "aras": {
            "name": "Aras Innovator",
            "fields": ["server_url", "username", "password", "database"],
            "description": "Aras Innovator open-source PLM"
        },
        "codebeamer": {
            "name": "Codebeamer (PTC)",
            "fields": ["server_url", "username", "password", "api_version"],
            "description": "PTC Codebeamer ALM/PLM via REST API"
        },
        "enovia": {
            "name": "ENOVIA",
            "fields": ["server_url", "username", "password", "security_context"],
            "description": "Dassault ENOVIA collaborative platform"
        }
    }
