import logging
import os
from fastapi import APIRouter, Body, Depends, HTTPException
from starlette.requests import Request
from pydantic import BaseModel
import neo4j
from datetime import datetime
from sqlalchemy.orm import Session

from core.crypto import decrypt_json, encrypt_json
from core.db_session import get_db
from models.configuration_models import EncryptedConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["Configuration Management"])

class Neo4jConfig(BaseModel):
    uri: str
    username: str
    password: str
    database: str = "neo4j"


class OpenSearchConfig(BaseModel):
    url: str
    username: str | None = None
    password: str | None = None
    verify_certs: bool = True
    timeout_s: float = 5.0

class ConfigResponse(BaseModel):
    status: str
    message: str
    timestamp: str


class CorsConfig(BaseModel):
    allowed_origins: list[str]


class WorkflowDefaultsConfig(BaseModel):
    source_endpoint_placeholder: str | None = None
    source_endpoints: dict[str, str] = {}
    target_endpoints: dict[str, str] = {}


class FilesystemAccessConfig(BaseModel):
    """Server-controlled allowlist for local file access (dev / on-prem).

    This is intentionally NOT part of the user-entered data source record.
    Data sources may reference local file paths, but the backend must decide
    which roots are permitted to be read.
    """

    allowed_local_roots: list[str] = []

@router.get(
    "/neo4j",
    summary="Get Neo4j Configuration",
    description="Get current Neo4j connection configuration (without sensitive data)."
)
async def get_neo4j_config(db: Session = Depends(get_db)):
    """Get current Neo4j configuration.

    Source of truth is the app DB (encrypted at rest). If no config exists yet,
    fall back to environment variables.
    """

    row = db.get(EncryptedConfig, "neo4j")
    if row is not None:
        try:
            payload = decrypt_json(row.ciphertext)
            uri = str(payload.get("uri") or "").strip()
            username = str(payload.get("username") or "").strip()
            database = str(payload.get("database") or "neo4j").strip() or "neo4j"
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to decrypt stored Neo4j config: %s", exc)
            uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
            username = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j"
            database = os.getenv("NEO4J_DATABASE", "neo4j")
    else:
        uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
        username = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j"
        database = os.getenv("NEO4J_DATABASE", "neo4j")

    # Test connection and get detailed result
    connection_result = await test_neo4j_connection(db=db)
    
    return {
        "uri": uri,
        "username": username,
        "database": database,
        "connection_status": "connected" if connection_result.connected else "disconnected",
        "error_type": connection_result.error_type,
        "error_message": connection_result.error_message,
    }

@router.post(
    "/neo4j",
    response_model=ConfigResponse,
    summary="Update Neo4j Configuration",
    description="Update Neo4j connection settings and test the connection."
)
async def update_neo4j_config(config: Neo4jConfig, request: Request, db: Session = Depends(get_db)):
    """Update Neo4j configuration, persist encrypted config, and refresh runtime driver."""
    try:
        # Preserve existing password if client omits it (UI does not load password).
        incoming_password = (config.password or "").strip()
        if not incoming_password:
            existing = db.get(EncryptedConfig, "neo4j")
            if existing is not None:
                try:
                    existing_payload = decrypt_json(existing.ciphertext)
                    incoming_password = str(existing_payload.get("password") or "").strip()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.warning("Could not decrypt existing Neo4j config to preserve password: %s", exc)

        # Test the connection first
        test_driver = neo4j.AsyncGraphDatabase.driver(
            config.uri,
            auth=(config.username, incoming_password),
            database=config.database,
        )
        
        # Verify connection works
        async with test_driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
        
        await test_driver.close()

        payload = {
            "uri": config.uri,
            "username": config.username,
            "password": incoming_password,
            "database": config.database,
        }

        row = db.get(EncryptedConfig, "neo4j")
        if row is None:
            row = EncryptedConfig(key="neo4j", ciphertext=encrypt_json(payload))
            db.add(row)
        else:
            row.ciphertext = encrypt_json(payload)
        db.commit()

        # Refresh runtime driver so /health and graph services use the new config.
        old_driver = getattr(request.app.state, "driver", None)
        try:
            new_driver = neo4j.AsyncGraphDatabase.driver(
                config.uri,
                auth=neo4j.basic_auth(config.username, incoming_password),
                database=config.database,
            )
            await new_driver.verify_connectivity()
            request.app.state.driver = new_driver
            request.app.state.neo4j_ok = True
            # Best-effort close old driver
            if old_driver is not None:
                try:
                    await old_driver.close()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Neo4j config saved, but runtime driver refresh failed: %s", exc)
        
        return ConfigResponse(
            status="success",
            message="Neo4j configuration updated and connection verified successfully",
            timestamp=datetime.now().isoformat()
        )
        
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError, OSError, ValueError, RuntimeError) as exc:
        logger.error("Failed to update Neo4j configuration: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect to Neo4j with provided settings: {str(exc)}"
        ) from exc

@router.post(
    "/neo4j/test",
    response_model=ConfigResponse,
    summary="Test Neo4j Connection",
    description="Test Neo4j connection with provided settings without saving."
)
async def test_neo4j_config(config: Neo4jConfig):
    """Test Neo4j connection without saving configuration"""
    try:
        test_driver = neo4j.AsyncGraphDatabase.driver(
            config.uri,
            auth=(config.username, config.password),
            database=config.database
        )
        
        async with test_driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
            
            # Get some basic info
            info_result = await session.run("CALL dbms.components() YIELD versions RETURN versions[0] as version")
            version_record = await info_result.single()
            version = version_record["version"] if version_record else "unknown"
        
        await test_driver.close()
        
        return ConfigResponse(
            status="success",
            message=f"Connection successful. Neo4j version: {version}",
            timestamp=datetime.now().isoformat()
        )
        
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError, OSError, ValueError, RuntimeError) as exc:
        logger.error("Neo4j connection test failed: %s", exc)
        return ConfigResponse(
            status="failed",
            message=f"Connection failed: {str(exc)}",
            timestamp=datetime.now().isoformat()
        )

@router.get(
    "/environment",
    summary="Get Environment Status",
    description="Get current environment configuration status."
)
async def get_environment_status():
    """Get environment configuration status"""
    opensearch_url = os.getenv("OPENSEARCH_URL") or os.getenv("OPENSEARCH_HOSTS")
    return {
        "neo4j": {
            "configured": bool(os.getenv("NEO4J_URI")),
            "uri": os.getenv("NEO4J_URI", "Not configured"),
            "database": os.getenv("NEO4J_DATABASE", "neo4j"),
        },
        "opensearch": {
            "configured": bool(opensearch_url),
            "url": opensearch_url or "Not configured",
        },
    }


@router.get(
    "/cors",
    summary="Get CORS Configuration",
    description="Get current CORS configuration (allowed origins).",
)
async def get_cors_config(db: Session = Depends(get_db)):
    row = db.get(EncryptedConfig, "cors")
    if row is not None:
        try:
            payload = decrypt_json(row.ciphertext)
            allowed = payload.get("allowed_origins") if isinstance(payload, dict) else None
            if isinstance(allowed, list):
                cleaned = [str(o).strip() for o in allowed if str(o).strip()]
                return {"allowed_origins": cleaned}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to decrypt stored CORS config: %s", exc)

    env_origins = [
        origin.strip()
        for origin in (os.getenv("ALLOWED_ORIGINS") or "").split(",")
        if origin.strip()
    ]
    if env_origins:
        return {"allowed_origins": env_origins}

    return {
        "allowed_origins": [
            "http://localhost:3000",
            "http://localhost:8011",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:5176",
        ]
    }


@router.post(
    "/cors",
    response_model=ConfigResponse,
    summary="Update CORS Configuration",
    description="Update CORS allowed origins (stored encrypted in DB).",
)
async def update_cors_config(config: CorsConfig, db: Session = Depends(get_db)):
    allowed = [str(o).strip() for o in (config.allowed_origins or []) if str(o).strip()]
    # De-dupe while preserving order.
    seen: set[str] = set()
    allowed_unique: list[str] = []
    for origin in allowed:
        if origin in seen:
            continue
        seen.add(origin)
        allowed_unique.append(origin)

    payload = {"allowed_origins": allowed_unique}
    row = db.get(EncryptedConfig, "cors")
    if row is None:
        row = EncryptedConfig(key="cors", ciphertext=encrypt_json(payload))
        db.add(row)
    else:
        row.ciphertext = encrypt_json(payload)
    db.commit()

    return ConfigResponse(
        status="success",
        message="CORS configuration updated successfully",
        timestamp=datetime.now().isoformat(),
    )


@router.get(
    "/system",
    summary="Get System Configuration",
    description="Get the system configuration payload stored in DB.",
)
async def get_system_configuration(db: Session = Depends(get_db)):
    row = db.get(EncryptedConfig, "system_configuration")
    if row is not None:
        try:
            payload = decrypt_json(row.ciphertext)
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to decrypt stored system_configuration: %s", exc)
            return {}
    return {}


@router.post(
    "/system",
    response_model=ConfigResponse,
    summary="Update System Configuration",
    description="Replace the system configuration payload (stored encrypted in DB).",
)
async def update_system_configuration(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="System configuration must be a JSON object")

    row = db.get(EncryptedConfig, "system_configuration")
    if row is None:
        row = EncryptedConfig(key="system_configuration", ciphertext=encrypt_json(payload))
        db.add(row)
    else:
        row.ciphertext = encrypt_json(payload)
    db.commit()

    return ConfigResponse(
        status="success",
        message="System configuration updated successfully",
        timestamp=datetime.now().isoformat(),
    )


@router.get(
    "/filesystem",
    summary="Get Filesystem Access Configuration",
    description="Get the server-controlled allowlist for local file access (stored in system_configuration).",
)
async def get_filesystem_access_config(db: Session = Depends(get_db)):
    row = db.get(EncryptedConfig, "system_configuration")
    payload: dict = {}
    if row is not None:
        try:
            decrypted = decrypt_json(row.ciphertext)
            payload = decrypted if isinstance(decrypted, dict) else {}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to decrypt stored system_configuration: %s", exc)

    fs_cfg = payload.get("filesystem") if isinstance(payload, dict) else None
    if not isinstance(fs_cfg, dict):
        fs_cfg = {}

    roots = fs_cfg.get("allowed_local_roots")
    if isinstance(roots, list):
        cleaned = [str(p).strip() for p in roots if str(p).strip()]
    else:
        cleaned = []
    return {"allowed_local_roots": cleaned}


@router.post(
    "/filesystem",
    response_model=ConfigResponse,
    summary="Update Filesystem Access Configuration",
    description="Update the server-controlled allowlist for local file access (stored in system_configuration).",
)
async def update_filesystem_access_config(config: FilesystemAccessConfig, db: Session = Depends(get_db)):
    # Load existing system_configuration (or start from empty object).
    current: dict = {}
    row = db.get(EncryptedConfig, "system_configuration")
    if row is not None:
        try:
            decrypted = decrypt_json(row.ciphertext)
            current = decrypted if isinstance(decrypted, dict) else {}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to decrypt stored system_configuration for filesystem update: %s", exc)
            current = {}

    cleaned = [str(p).strip() for p in (config.allowed_local_roots or []) if str(p).strip()]
    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for p in cleaned:
        if p in seen:
            continue
        seen.add(p)
        unique.append(p)

    fs_cfg = current.get("filesystem")
    if not isinstance(fs_cfg, dict):
        fs_cfg = {}
    fs_cfg["allowed_local_roots"] = unique
    current["filesystem"] = fs_cfg

    if row is None:
        row = EncryptedConfig(key="system_configuration", ciphertext=encrypt_json(current))
        db.add(row)
    else:
        row.ciphertext = encrypt_json(current)
    db.commit()

    return ConfigResponse(
        status="success",
        message="Filesystem access configuration updated successfully",
        timestamp=datetime.now().isoformat(),
    )


@router.get(
    "/workflow-defaults",
    summary="Get Workflow Defaults",
    description="Get default source/target endpoints used to prefill Workflow Manager forms.",
)
async def get_workflow_defaults(db: Session = Depends(get_db)):
    row = db.get(EncryptedConfig, "workflow_defaults")
    if row is not None:
        try:
            payload = decrypt_json(row.ciphertext)
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to decrypt stored workflow_defaults: %s", exc)
            return {}
    return {}


@router.post(
    "/workflow-defaults",
    response_model=ConfigResponse,
    summary="Update Workflow Defaults",
    description="Update default source/target endpoints used by Workflow Manager (stored encrypted in DB).",
)
async def update_workflow_defaults(config: WorkflowDefaultsConfig, db: Session = Depends(get_db)):
    def _clean_map(value: dict[str, str]) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        out: dict[str, str] = {}
        for k, v in value.items():
            key = str(k).strip()
            if not key:
                continue
            out[key] = str(v).strip() if v is not None else ""
        return out

    payload = {
        "source_endpoint_placeholder": (config.source_endpoint_placeholder or "").strip() or "https://<host>/api",
        "source_endpoints": _clean_map(config.source_endpoints or {}),
        "target_endpoints": _clean_map(config.target_endpoints or {}),
    }

    row = db.get(EncryptedConfig, "workflow_defaults")
    if row is None:
        row = EncryptedConfig(key="workflow_defaults", ciphertext=encrypt_json(payload))
        db.add(row)
    else:
        row.ciphertext = encrypt_json(payload)
    db.commit()

    return ConfigResponse(
        status="success",
        message="Workflow defaults updated successfully",
        timestamp=datetime.now().isoformat(),
    )


@router.get(
    "/runtime",
    summary="Get Runtime Configuration Summary",
    description="Return a non-secret configuration summary for the frontend.",
)
async def get_runtime_config_summary(db: Session = Depends(get_db)):
    # Neo4j summary (no password)
    neo4j_row = db.get(EncryptedConfig, "neo4j")
    neo4j_payload: dict = {}
    if neo4j_row is not None:
        try:
            neo4j_payload = decrypt_json(neo4j_row.ciphertext)
        except Exception:  # pylint: disable=broad-exception-caught
            neo4j_payload = {}
    neo4j_uri = str((neo4j_payload or {}).get("uri") or os.getenv("NEO4J_URI") or "").strip() or None
    neo4j_user = str((neo4j_payload or {}).get("username") or os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j").strip()
    neo4j_db = str((neo4j_payload or {}).get("database") or os.getenv("NEO4J_DATABASE") or "neo4j").strip() or "neo4j"

    # OpenSearch summary (no password)
    os_row = db.get(EncryptedConfig, "opensearch")
    os_payload: dict = {}
    if os_row is not None:
        try:
            os_payload = decrypt_json(os_row.ciphertext)
        except Exception:  # pylint: disable=broad-exception-caught
            os_payload = {}
    os_url = str((os_payload or {}).get("url") or os.getenv("OPENSEARCH_URL") or "").strip() or None
    os_user = (str((os_payload or {}).get("username") or os.getenv("OPENSEARCH_USERNAME") or "").strip() or None)
    os_verify = bool((os_payload or {}).get("verify_certs", True))
    try:
        os_timeout = float((os_payload or {}).get("timeout_s", os.getenv("OPENSEARCH_TIMEOUT_S") or 5.0) or 5.0)
    except Exception:  # pylint: disable=broad-exception-caught
        os_timeout = 5.0

    cors = await get_cors_config(db=db)
    system_cfg = await get_system_configuration(db=db)
    workflow_defaults = await get_workflow_defaults(db=db)

    return {
        "neo4j": {
            "configured": bool(neo4j_uri),
            "uri": neo4j_uri or "",
            "username": neo4j_user,
            "database": neo4j_db,
        },
        "opensearch": {
            "configured": bool(os_url),
            "url": os_url or "",
            "username": os_user,
            "verify_certs": os_verify,
            "timeout_s": os_timeout,
        },
        "cors": cors,
        "system_configuration": system_cfg,
        "workflow_defaults": workflow_defaults,
    }


@router.get(
    "/opensearch",
    summary="Get OpenSearch Configuration",
    description="Get current OpenSearch connection configuration (without sensitive data).",
)
async def get_opensearch_config(db: Session = Depends(get_db)):
    """Get current OpenSearch configuration.

    Source of truth is the app DB (encrypted at rest). If no config exists yet,
    fall back to environment variables.
    """

    row = db.get(EncryptedConfig, "opensearch")
    if row is not None:
        try:
            payload = decrypt_json(row.ciphertext)
            url = str(payload.get("url") or payload.get("endpoint") or "").strip()
            username = str(payload.get("username") or "").strip() or None
            verify_certs = bool(payload.get("verify_certs", True))
            timeout_s = float(payload.get("timeout_s", 5.0) or 5.0)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to decrypt stored OpenSearch config: %s", exc)
            url = (os.getenv("OPENSEARCH_URL") or "").strip()
            username = (os.getenv("OPENSEARCH_USERNAME") or "").strip() or None
            verify_certs = (os.getenv("OPENSEARCH_VERIFY_CERTS") or "true").strip().lower() not in {
                "0",
                "false",
                "no",
            }
            timeout_s = float((os.getenv("OPENSEARCH_TIMEOUT_S") or "5").strip() or 5)
    else:
        url = (os.getenv("OPENSEARCH_URL") or "").strip()
        username = (os.getenv("OPENSEARCH_USERNAME") or "").strip() or None
        verify_certs = (os.getenv("OPENSEARCH_VERIFY_CERTS") or "true").strip().lower() not in {
            "0",
            "false",
            "no",
        }
        timeout_s = float((os.getenv("OPENSEARCH_TIMEOUT_S") or "5").strip() or 5)

    return {
        "url": url,
        "username": username,
        "verify_certs": verify_certs,
        "timeout_s": timeout_s,
        "connection_status": "connected" if await test_opensearch_connection(db=db) else "disconnected",
    }


@router.post(
    "/opensearch",
    response_model=ConfigResponse,
    summary="Update OpenSearch Configuration",
    description="Update OpenSearch connection settings and test the connection.",
)
async def update_opensearch_config(config: OpenSearchConfig, db: Session = Depends(get_db)):
    """Update OpenSearch configuration, persist encrypted config."""
    try:
        # Preserve existing password if omitted or masked.
        incoming_password = (config.password or "").strip()
        if (not incoming_password) or incoming_password == "***":
            existing = db.get(EncryptedConfig, "opensearch")
            if existing is not None:
                try:
                    existing_payload = decrypt_json(existing.ciphertext)
                    incoming_password = str(existing_payload.get("password") or "").strip()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.warning("Could not decrypt existing OpenSearch config to preserve password: %s", exc)

        # Test connection before saving.
        ok = await test_opensearch_connection(
            config={
                "url": config.url,
                "username": (config.username or "").strip() or None,
                "password": incoming_password,
                "verify_certs": bool(config.verify_certs),
                "timeout_s": float(config.timeout_s or 5.0),
            }
        )
        if not ok:
            raise RuntimeError("Failed to connect to OpenSearch with provided settings")

        payload = {
            "url": config.url,
            "username": (config.username or "").strip() or None,
            "password": incoming_password,
            "verify_certs": bool(config.verify_certs),
            "timeout_s": float(config.timeout_s or 5.0),
        }

        row = db.get(EncryptedConfig, "opensearch")
        if row is None:
            row = EncryptedConfig(key="opensearch", ciphertext=encrypt_json(payload))
            db.add(row)
        else:
            row.ciphertext = encrypt_json(payload)
        db.commit()

        return ConfigResponse(
            status="success",
            message="OpenSearch configuration updated and connection verified successfully",
            timestamp=datetime.now().isoformat(),
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Failed to update OpenSearch configuration: %s", exc)
        raise HTTPException(status_code=400, detail=f"Failed to connect to OpenSearch with provided settings: {str(exc)}") from exc


@router.post(
    "/opensearch/test",
    response_model=ConfigResponse,
    summary="Test OpenSearch Connection",
    description="Test OpenSearch connection with provided settings without saving.",
)
async def test_opensearch_config(config: OpenSearchConfig):
    """Test OpenSearch connection without saving configuration."""
    try:
        ok = await test_opensearch_connection(
            config={
                "url": config.url,
                "username": (config.username or "").strip() or None,
                "password": (config.password or "").strip() or None,
                "verify_certs": bool(config.verify_certs),
                "timeout_s": float(config.timeout_s or 5.0),
            }
        )
        if ok:
            return ConfigResponse(
                status="success",
                message="Connection successful.",
                timestamp=datetime.now().isoformat(),
            )

        return ConfigResponse(
            status="failed",
            message="Connection failed.",
            timestamp=datetime.now().isoformat(),
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("OpenSearch connection test failed: %s", exc)
        return ConfigResponse(
            status="failed",
            message=f"Connection failed: {str(exc)}",
            timestamp=datetime.now().isoformat(),
        )


async def test_opensearch_connection(db: Session | None = None, config: dict[str, object] | None = None) -> bool:
    """Internal helper to test current OpenSearch connection.

    Prefer explicit `config` when provided; otherwise prefer DB-stored config, then env.
    """
    try:
        url = None
        username = None
        password = None
        verify_certs = True
        timeout_s = 5.0

        if config is not None:
            url = str(config.get("url") or "").strip() or None
            username = str(config.get("username") or "").strip() or None
            password = str(config.get("password") or "").strip() or None
            verify_certs = bool(config.get("verify_certs", True))
            timeout_raw = config.get("timeout_s", 5.0)
            try:
                timeout_s = float(timeout_raw)  # type: ignore[arg-type]
            except Exception:  # pylint: disable=broad-exception-caught
                timeout_s = 5.0
        elif db is not None:
            row = db.get(EncryptedConfig, "opensearch")
            if row is not None:
                try:
                    payload = decrypt_json(row.ciphertext)
                    url = str(payload.get("url") or payload.get("endpoint") or "").strip() or None
                    username = str(payload.get("username") or "").strip() or None
                    password = str(payload.get("password") or "").strip() or None
                    verify_certs = bool(payload.get("verify_certs", True))
                    timeout_s = float(payload.get("timeout_s", 5.0) or 5.0)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Failed to decrypt stored OpenSearch config: %s", exc)

        if not url:
            url = (os.getenv("OPENSEARCH_URL") or "").strip() or None
        if not username:
            username = (os.getenv("OPENSEARCH_USERNAME") or "").strip() or None
        if not password:
            password = (os.getenv("OPENSEARCH_PASSWORD") or "").strip() or None

        if not url:
            return False

        from urllib.parse import urlparse
        from opensearchpy import OpenSearch  # type: ignore

        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 9200)

        use_ssl = parsed.scheme == "https"
        http_auth = None
        if username or password:
            http_auth = (username or "", password or "")

        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            timeout=timeout_s,
        )
        _ = client.info()
        return True
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("OpenSearch connection test failed: %s", exc)
        return False

class Neo4jConnectionResult:
    """Result of Neo4j connection test with detailed error info."""
    def __init__(self, connected: bool, error_type: str | None = None, error_message: str | None = None):
        self.connected = connected
        self.error_type = error_type  # 'no_config', 'service_unavailable', 'auth_failed', 'unknown'
        self.error_message = error_message
    
    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "error_type": self.error_type,
            "error_message": self.error_message
        }


async def test_neo4j_connection(db: Session | None = None) -> Neo4jConnectionResult:
    """Internal helper to test current Neo4j connection.

    Prefer DB-stored config when available.
    Returns Neo4jConnectionResult with detailed error information.
    """
    try:
        uri = None
        username = None
        password = None
        database = None

        if db is not None:
            row = db.get(EncryptedConfig, "neo4j")
            if row is not None:
                try:
                    payload = decrypt_json(row.ciphertext)
                    uri = str(payload.get("uri") or "").strip() or None
                    username = str(payload.get("username") or "").strip() or None
                    password = str(payload.get("password") or "").strip() or None
                    database = str(payload.get("database") or "").strip() or None
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Failed to decrypt stored Neo4j config: %s", exc)

        if not uri:
            uri = os.getenv("NEO4J_URI")
        if not username:
            username = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
        if not password:
            password = os.getenv("NEO4J_PASSWORD")
        if not database:
            database = os.getenv("NEO4J_DATABASE")

        if not uri or not username or not password:
            return Neo4jConnectionResult(
                connected=False,
                error_type="no_config",
                error_message="Neo4j connection not configured. Please set up Neo4j in Data Configuration."
            )

        uri_str: str = uri
        username_str: str = username
        password_str: str = password
            
        test_driver = neo4j.AsyncGraphDatabase.driver(uri_str, auth=(username_str, password_str))

        async with test_driver.session(database=(database or None)) as session:
            await session.run("RETURN 1")
        
        await test_driver.close()
        return Neo4jConnectionResult(connected=True)
        
    except (OSError, ConnectionRefusedError) as exc:
        logger.error("Neo4j service unavailable: %s", exc)
        return Neo4jConnectionResult(
            connected=False,
            error_type="service_unavailable",
            error_message="Neo4j service is not running. Please start Neo4j in Neo4j Desktop or ensure the service is running."
        )
    except neo4j.exceptions.AuthError as exc:
        logger.error("Neo4j authentication failed: %s", exc)
        return Neo4jConnectionResult(
            connected=False,
            error_type="auth_failed",
            error_message="Neo4j authentication failed. Please check your username and password in Data Configuration."
        )
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError, ValueError, RuntimeError) as exc:
        logger.error("Neo4j connection test failed: %s", exc)
        return Neo4jConnectionResult(
            connected=False,
            error_type="unknown",
            error_message=f"Neo4j connection failed: {str(exc)}"
        )
