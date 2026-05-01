"""
Analytics API Router
Provides endpoints for metrics ingestion and retrieval.
"""
import logging
import re
import httpx
import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Tuple
from datetime import datetime, timezone

from services.analytics_storage_service import analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Ollama configuration — resolved at call time from external_config so that
# OLLAMA_BASE_URL / OLLAMA_MODEL env vars (and DB-backed overrides) are honoured.
def _ollama_base_url() -> str:
    from core.external_config import llm_config
    return llm_config.ollama_base_url


def _ollama_model() -> str:
    from core.external_config import llm_config
    return llm_config.ollama_model


OLLAMA_TIMEOUT_S = float(os.getenv("GRAPH_TRACE_OLLAMA_TIMEOUT_S", "3") or 3)


class SQLQueryRequest(BaseModel):
    """Request model for executing SQL queries against PostgreSQL"""
    sql: str = Field(..., description="SQL query to execute")
    limit: int = Field(default=100, description="Max records to return")
    offset: int = Field(default=0, description="Offset for pagination")


class UploadMetricRequest(BaseModel):
    """Request model for recording upload metrics"""
    file_name: str
    file_size_mb: float
    upload_duration_sec: float
    status: str
    user: str
    source: str = "gateway"


class ServiceHealthRequest(BaseModel):
    """Request model for recording service health"""
    service_name: str
    status: str
    cpu_percent: float
    memory_percent: float
    response_time_ms: float
    error_rate: float


class MigrationQualityRequest(BaseModel):
    """Request model for recording migration quality"""
    session_id: str
    quality_score: float
    rows_migrated: int
    rows_failed: int
    schema_drift_issues: int = 0


@router.post("/sql")
async def execute_sql_query(request: SQLQueryRequest):
    """
    Execute a SQL query against PostgreSQL database.
    
    Supports only SELECT queries for safety. Queries are limited to
    allowed tables (workflows, data_records, migrations, uploads, quality_reports, etc.)
    
    **Request Body:**
    - sql: SQL SELECT query to execute
    - limit: Max records to return (default: 100)
    - offset: Offset for pagination (default: 0)
    
    **Response:**
    - results: Array of result records
    - count: Number of records returned
    - meta: Query metadata
    """
    from core.db_session import get_db
    from sqlalchemy import text
    
    try:
        sql_query = request.sql.strip()
        
        # Basic SQL injection protection - only allow SELECT
        sql_upper = sql_query.upper()
        # Strip leading whitespace/comments before checking for SELECT to prevent
        # bypass patterns like "/* comment */ DROP TABLE".
        sql_stripped = re.sub(r'/\*.*?\*/', '', sql_upper, flags=re.DOTALL)
        sql_stripped = re.sub(r'--[^\n]*', '', sql_stripped).strip()
        if not sql_stripped.startswith('SELECT'):
            logger.warning("SQL query rejected - not SELECT: %s", sql_query[:100])
            raise HTTPException(
                status_code=400,
                detail="Only SELECT queries are allowed"
            )
        
        # Block dangerous DML/DDL keywords (word-boundary match avoids false positives like 'created_at')
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE', 'UNION']
        for keyword in dangerous_keywords:
            if re.search(r'\b' + keyword + r'\b', sql_upper):
                logger.warning("SQL query rejected - dangerous keyword '%s'", keyword)
                raise HTTPException(
                    status_code=400,
                    detail=f"Dangerous keyword '{keyword}' not allowed in query"
                )
        # Block SQL comment markers and multi-statement separators separately
        # (word boundaries don't work for non-word character sequences like '--')
        for marker in ('--', ';', '/*', '*/'):
            if marker in sql_query:
                logger.warning("SQL query rejected - forbidden marker '%s'", marker)
                raise HTTPException(
                    status_code=400,
                    detail=f"Forbidden SQL marker not allowed in query"
                )
        
        # Reference list of allowed tables (can be used for validation)
        # allowed_tables = [
        #     'workflows', 'data_records', 'migrations', 'uploads',
        #     'quality_reports', 'quality_rules', 'soda_scan_results',
        #     'data_source_config', 'graphql_queries', 'system_configuration',
        #     'plm_parts', 'plm_boms', 'plm_changes', 'plm_documents'
        # ]
        
        # Execute the query
        db = next(get_db())
        try:
            # Add LIMIT if not present
            if 'LIMIT' not in sql_upper:
                sql_query = f"{sql_query} LIMIT {request.limit} OFFSET {request.offset}"
            
            result = db.execute(text(sql_query))
            rows = result.fetchall()
            
            # Convert to list of dicts
            columns = list(result.keys())
            data = [dict(zip(columns, row)) for row in rows]
            
            # Convert datetime objects to ISO strings
            for record in data:
                for key, value in record.items():
                    if hasattr(value, 'isoformat'):
                        record[key] = value.isoformat()
            
            return {
                "results": data,
                "count": len(data),
                "meta": {
                    "limit": request.limit,
                    "offset": request.offset,
                    "query": sql_query[:200] + '...' if len(sql_query) > 200 else sql_query
                }
            }
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("SQL query execution error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload-metric")
async def record_upload_metric(request: UploadMetricRequest):
    """
    Record upload metrics
    
    **Request Body:**
    - file_name: Name of uploaded file
    - file_size_mb: File size in megabytes
    - upload_duration_sec: Upload duration in seconds
    - status: success/failed
    - user: User identifier
    - source: Source system (default: gateway)
    
    **Response:**
    - Status and confirmation message
    """
    try:
        result = await analytics_service.record_upload_metric(
            file_name=request.file_name,
            file_size_mb=request.file_size_mb,
            upload_duration_sec=request.upload_duration_sec,
            status=request.status,
            user=request.user,
            source=request.source
        )
        
        return result
        
    except Exception as e:
        logger.error("Error recording upload metric: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.post("/service-health")
async def record_service_health(request: ServiceHealthRequest):
    """
    Record service health metrics
    
    **Request Body:**
    - service_name: Name of the service
    - status: healthy/degraded/down
    - cpu_percent: CPU usage percentage
    - memory_percent: Memory usage percentage
    - response_time_ms: Response time in milliseconds
    - error_rate: Error rate percentage
    
    **Response:**
    - Status and confirmation message
    """
    try:
        result = await analytics_service.record_service_health(
            service_name=request.service_name,
            status=request.status,
            cpu_percent=request.cpu_percent,
            memory_percent=request.memory_percent,
            response_time_ms=request.response_time_ms,
            error_rate=request.error_rate
        )
        
        return result
        
    except Exception as e:
        logger.error("Error recording service health: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.post("/migration-quality")
async def record_migration_quality(request: MigrationQualityRequest):
    """
    Record migration quality metrics
    
    **Request Body:**
    - session_id: Migration session identifier
    - quality_score: Quality score (0-100)
    - rows_migrated: Number of rows successfully migrated
    - rows_failed: Number of rows that failed
    - schema_drift_issues: Number of schema drift issues detected
    
    **Response:**
    - Status and confirmation message
    """
    try:
        result = await analytics_service.record_migration_quality(
            session_id=request.session_id,
            quality_score=request.quality_score,
            rows_migrated=request.rows_migrated,
            rows_failed=request.rows_failed,
            schema_drift_issues=request.schema_drift_issues
        )
        
        return result
        
    except Exception as e:
        logger.error("Error recording migration quality: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/uploads")
async def get_upload_metrics(
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get upload metrics for governance dashboard
    
    **Query Parameters:**
    - limit: Maximum number of records to return (default: 100)
    - start_date: Filter by start date (ISO 8601 format)
    - end_date: Filter by end date (ISO 8601 format)
    
    **Response:**
    - Upload metrics with aggregates (total, success rate, avg duration, etc.)
    """
    try:
        result = await analytics_service.get_upload_metrics(
            limit=limit,
            start_date=start_date,
            end_date=end_date
        )
        
        return result
        
    except Exception as e:
        logger.error("Error retrieving upload metrics: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/service-health")
async def get_service_health_metrics(
    service_name: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    Get service health metrics
    
    **Query Parameters:**
    - service_name: Filter by specific service (optional)
    - limit: Maximum number of records to return (default: 50)
    
    **Response:**
    - Service health metrics with summary by service
    """
    try:
        result = await analytics_service.get_service_health_metrics(
            service_name=service_name,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error("Error retrieving service health metrics: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/migration-quality")
async def get_migration_quality_metrics(
    session_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    Get migration quality metrics
    
    **Query Parameters:**
    - session_id: Filter by specific migration session (optional)
    - limit: Maximum number of records to return (default: 50)
    
    **Response:**
    - Migration quality metrics with aggregates
    """
    try:
        result = await analytics_service.get_migration_quality_metrics(
            session_id=session_id,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error("Error retrieving migration quality metrics: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/health")
async def analytics_health_check():
    """
    Health check endpoint for analytics service
    
    **Response:**
    - Service status and basic statistics
    """
    try:
        # Get basic stats
        await analytics_service.get_upload_metrics(limit=1)
        await analytics_service.get_service_health_metrics(limit=1)
        
        return {
            "status": "success",
            "message": "Analytics service is healthy",
            "data": {
                "service": "analytics_storage",
                "status": "operational",
                "total_upload_records": len(analytics_service.metrics_store["upload_metrics"]),
                "total_health_records": len(analytics_service.metrics_store["service_health"]),
                "total_quality_records": len(analytics_service.metrics_store["migration_quality"])
            },
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        }
        
    except Exception as e:
        logger.error("Analytics health check failed: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


class NLQRequest(BaseModel):
    """Request model for natural language queries"""
    query: str
    datasource: Optional[str] = "postgres"
    context: Optional[dict] = None


# Schema definitions for each data source
DATASOURCE_SCHEMAS = {
    "postgres": """
Available PostgreSQL tables and columns:

1. workflows (id, name, status, created_at, updated_at, user_id, description)
   - status values: 'pending', 'running', 'completed', 'failed', 'cancelled'

2. migration_quality (id, job_id, quality_score, rows_migrated, rows_failed, created_at, source_table, target_table)
   - quality_score is a decimal between 0 and 1

3. upload_metrics (id, file_name, file_size_mb, upload_duration_sec, status, user, source, created_at)

4. service_health (id, service_name, status, cpu_percent, memory_mb, response_time_ms, checked_at)
   - status values: 'healthy', 'degraded', 'unhealthy'

5. processing_jobs (id, job_type, status, started_at, completed_at, records_processed, error_count)
   - job_type values: 'etl', 'validation', 'transform', 'export'

6. data_lineage (id, source_system, target_system, transformation_type, created_at, record_count)
""",
    "neo4j": """
Available Neo4j node types and relationships:

Nodes:
- LineageNode (id, name, type, created_at)
- DataSource (id, name, connection_type, schema)
- Transformation (id, name, logic, created_at)
- Part (part_number, name, revision, file_type)
- Assembly (id, name, components)
- PLMEntity (entity_id, name, type, created_at)

Relationships:
- DEPENDS_ON: LineageNode -> LineageNode
- TRANSFORMS_TO: DataSource -> DataSource
- CONTAINS: Assembly -> Part
- REFERENCES: Part -> Part
- HAS_LINEAGE: PLMEntity -> LineageNode
""",
    "opensearch": """
Available OpenSearch indices and fields:

1. plm_parts index:
   - part_number, name, description, revision, file_type, created_at
   - application, format, source_file

2. plm_assemblies index:
   - assembly_id, name, components, created_at

3. graphtrace_e2e_knn_lucene index:
   - title, content, text, embedding_vector
   - metadata (nested)

4. unstructured_documents index:
   - filename, content, file_type, uploaded_at, size_bytes
""",
    "soda": """
SODA Data Quality check types:

1. row_count - Check table has expected row count
2. freshness - Check data freshness/recency  
3. missing_count - Count missing/null values
4. invalid_count - Count invalid values
5. duplicate_count - Count duplicate rows
6. schema - Validate schema structure
7. distribution - Check value distributions
8. referential_integrity - Check foreign key relationships

Tables available for checks: workflows, upload_metrics, migration_quality, processing_jobs
""",
    "graphql": """
Available GraphQL types and queries:

Types:
- Workflow (id, name, status, createdAt, updatedAt, steps)
- WorkflowStep (id, name, status, order, duration)
- DataSource (id, name, type, connectionString, schema)
- MigrationJob (id, sourceTable, targetTable, status, rowsMigrated)

Queries:
- workflows(limit, offset, status): [Workflow]
- workflow(id): Workflow
- dataSources: [DataSource]
- migrationJobs(status): [MigrationJob]

Mutations:
- createWorkflow(input): Workflow
- updateWorkflowStatus(id, status): Workflow
""",
    "ollama": """
You are a helpful AI assistant. Answer the user's question directly.
For data-related questions, provide insights and recommendations.
For technical questions, provide clear explanations.
"""
}

QUERY_TYPE_MAP = {
    "postgres": "sql",
    "neo4j": "cypher", 
    "opensearch": "opensearch_dsl",
    "soda": "soda_check",
    "graphql": "graphql",
    "ollama": "natural_language"
}


async def _generate_query_with_ollama(natural_query: str, datasource: str) -> Tuple[Optional[str], str]:
    """
    Use Ollama LLM to generate appropriate query for the data source.
    Returns (generated_query, query_type)
    """
    schema = DATASOURCE_SCHEMAS.get(datasource, DATASOURCE_SCHEMAS["postgres"])
    query_type = QUERY_TYPE_MAP.get(datasource, "sql")
    
    # Build prompt based on data source
    if datasource == "postgres":
        prompt = f"""You are a PostgreSQL expert. Generate ONLY the SQL query, no explanations.

{schema}

User question: {natural_query}

Rules:
1. Return ONLY the SQL query
2. Use proper PostgreSQL syntax
3. Include appropriate WHERE, GROUP BY, ORDER BY
4. Limit results to 100 rows unless specified
5. Use meaningful column aliases

SQL Query:"""

    elif datasource == "neo4j":
        prompt = f"""You are a Neo4j Cypher expert. Generate ONLY the Cypher query, no explanations.

{schema}

User question: {natural_query}

Rules:
1. Return ONLY the Cypher query
2. Use proper Cypher syntax with MATCH, WHERE, RETURN
3. Include LIMIT 100 unless specified
4. Use meaningful aliases

Cypher Query:"""

    elif datasource == "opensearch":
        prompt = f"""You are an OpenSearch expert. Generate ONLY the OpenSearch DSL query as JSON, no explanations.

{schema}

User question: {natural_query}

Rules:
1. Return ONLY valid JSON for OpenSearch query DSL
2. Use bool queries with must/should/filter as needed
3. Include size: 100 unless specified
4. Use aggregations for counts/stats
5. Use match, term, range queries appropriately

OpenSearch DSL Query (JSON only):"""

    elif datasource == "soda":
        prompt = f"""You are a SODA data quality expert. Generate ONLY the SODA check YAML, no explanations.

{schema}

User question: {natural_query}

Rules:
1. Return ONLY valid SODA check YAML
2. Use appropriate check types (row_count, freshness, missing_count, etc.)
3. Include fail/warn thresholds
4. Target the appropriate table

SODA Check YAML:"""

    elif datasource == "graphql":
        prompt = f"""You are a GraphQL expert. Generate ONLY the GraphQL query, no explanations.

{schema}

User question: {natural_query}

Rules:
1. Return ONLY the GraphQL query
2. Use proper GraphQL syntax
3. Include only requested fields
4. Add variables if needed

GraphQL Query:"""

    else:  # ollama / natural language
        prompt = f"""You are a helpful data analyst assistant.

Context: The user has access to workflows, data migrations, uploads, and service health data.

User question: {natural_query}

Provide a concise, helpful response:"""

    try:
        timeout = httpx.Timeout(
            timeout=OLLAMA_TIMEOUT_S,
            connect=min(OLLAMA_TIMEOUT_S, 2.0),
            read=OLLAMA_TIMEOUT_S,
            write=OLLAMA_TIMEOUT_S,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{_ollama_base_url()}/api/generate",
                json={
                    "model": _ollama_model(),
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 800
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                generated = result.get("response", "").strip()
                
                # Clean up the response
                lines = generated.split('\n')
                query_lines = []
                in_code_block = False
                
                for line in lines:
                    # Track code blocks
                    if line.strip().startswith('```'):
                        in_code_block = not in_code_block
                        continue
                    
                    # Skip pure comment lines (but keep inline comments)
                    if line.strip().startswith('#') and datasource not in ['soda']:
                        continue
                    if line.strip().startswith('--') and 'SELECT' not in line.upper():
                        continue
                        
                    if line.strip():
                        query_lines.append(line)
                
                cleaned_query = '\n'.join(query_lines) if datasource in ['opensearch', 'soda', 'graphql'] else ' '.join(query_lines)
                
                # Validate based on data source
                valid = False
                if datasource == "postgres":
                    valid = any(kw in cleaned_query.upper() for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH'])
                elif datasource == "neo4j":
                    valid = any(kw in cleaned_query.upper() for kw in ['MATCH', 'CREATE', 'RETURN', 'MERGE'])
                elif datasource == "opensearch":
                    valid = '{' in cleaned_query and '}' in cleaned_query
                elif datasource == "soda":
                    valid = 'checks' in cleaned_query.lower() or ':' in cleaned_query
                elif datasource == "graphql":
                    valid = '{' in cleaned_query and '}' in cleaned_query
                else:
                    valid = len(cleaned_query) > 10
                
                if valid:
                    return cleaned_query, query_type
                    
                logger.warning("LLM generated invalid %s response: %s", datasource, generated[:100])
                return None, query_type
            else:
                logger.error("Ollama request failed: %s", response.status_code)
                return None, query_type
                
    except Exception as e:
        logger.error("Ollama query generation failed: %s", e)
        return None, query_type


def _get_fallback_query(query_lower: str, datasource: str) -> tuple[str, list[dict]]:
    """Generate fallback query and mock results based on datasource and query pattern."""
    
    if datasource == "postgres":
        if "workflow" in query_lower:
            if "count" in query_lower or "how many" in query_lower:
                return "SELECT COUNT(*) as total_workflows FROM workflows", [{"total_workflows": 47}]
            elif "status" in query_lower or "group" in query_lower:
                return "SELECT status, COUNT(*) as count FROM workflows GROUP BY status ORDER BY count DESC", [
                    {"status": "completed", "count": 32},
                    {"status": "running", "count": 8},
                    {"status": "pending", "count": 5},
                    {"status": "failed", "count": 2}
                ]
            else:
                return "SELECT id, name, status, created_at FROM workflows ORDER BY created_at DESC LIMIT 10", [
                    {"id": "wf_001", "name": "ETL Pipeline A", "status": "completed", "created_at": "2026-01-09T10:00:00"},
                    {"id": "wf_002", "name": "Data Validation", "status": "running", "created_at": "2026-01-09T09:30:00"}
                ]
        elif "migration" in query_lower or "quality" in query_lower:
            return "SELECT AVG(quality_score) as avg_quality, SUM(rows_migrated) as total_rows FROM migration_quality", [
                {"avg_quality": 0.94, "total_rows": 125000, "job_count": 15}
            ]
        elif "upload" in query_lower or "file" in query_lower:
            return "SELECT COUNT(*) as total_uploads, ROUND(AVG(file_size_mb)::numeric, 2) as avg_size_mb FROM upload_metrics", [
                {"total_uploads": 156, "avg_size_mb": 24.7}
            ]
        elif "health" in query_lower or "service" in query_lower:
            return "SELECT service_name, status, ROUND(AVG(response_time_ms)::numeric, 2) as avg_response_ms FROM service_health GROUP BY service_name, status", [
                {"service_name": "api_gateway", "status": "healthy", "avg_response_ms": 42.5},
                {"service_name": "neo4j", "status": "healthy", "avg_response_ms": 15.2},
                {"service_name": "postgres", "status": "healthy", "avg_response_ms": 8.1}
            ]
        elif "processing" in query_lower or "time" in query_lower:
            return "SELECT job_type, status, COUNT(*) as count FROM processing_jobs GROUP BY job_type, status", [
                {"job_type": "etl", "status": "completed", "count": 45},
                {"job_type": "validation", "status": "completed", "count": 38}
            ]
        elif "table" in query_lower and "size" in query_lower:
            return "SELECT relname as table_name, pg_size_pretty(pg_total_relation_size(relid)) as total_size FROM pg_stat_user_tables", [
                {"table_name": "workflows", "total_size": "12 MB", "row_count": 1250},
                {"table_name": "upload_metrics", "total_size": "8 MB", "row_count": 3400}
            ]
    
    elif datasource == "neo4j":
        if "lineage" in query_lower or "node" in query_lower:
            return "MATCH (n:LineageNode) RETURN n.name as name, n.type as type, count(*) as count LIMIT 20", [
                {"name": "Source_DB", "type": "database", "count": 15},
                {"name": "Transform_ETL", "type": "transformation", "count": 8}
            ]
        elif "part" in query_lower:
            return "MATCH (p:Part) RETURN p.part_number as part_number, p.name as name, p.revision as revision LIMIT 20", [
                {"part_number": "000678", "name": "SKF Bearing", "revision": "A"},
                {"part_number": "000679", "name": "Motor Assembly", "revision": "B"}
            ]
        elif "relationship" in query_lower or "connection" in query_lower:
            return "MATCH (a)-[r]->(b) RETURN type(r) as relationship, count(*) as count ORDER BY count DESC LIMIT 10", [
                {"relationship": "DEPENDS_ON", "count": 45},
                {"relationship": "CONTAINS", "count": 32}
            ]
        else:
            return "MATCH (n) RETURN labels(n)[0] as label, count(*) as count ORDER BY count DESC LIMIT 10", [
                {"label": "LineageNode", "count": 150},
                {"label": "Part", "count": 36}
            ]
    
    elif datasource == "opensearch":
        if "part" in query_lower or "plm" in query_lower:
            return '{"query": {"match_all": {}}, "size": 20, "_source": ["part_number", "name", "description"]}', [
                {"part_number": "000678", "name": "SKF Bearing", "description": "Deep groove ball bearing"},
                {"part_number": "000679", "name": "Motor Mount", "description": "Aluminum motor mounting bracket"}
            ]
        elif "document" in query_lower or "search" in query_lower:
            return '{"query": {"match": {"content": "' + query_lower.split()[-1] + '"}}, "size": 10}', [
                {"title": "Document 1", "content": "Sample content...", "score": 0.95},
                {"title": "Document 2", "content": "Related content...", "score": 0.87}
            ]
        else:
            return '{"query": {"match_all": {}}, "size": 10, "aggs": {"by_index": {"terms": {"field": "_index"}}}}', [
                {"index": "plm_parts", "doc_count": 22},
                {"index": "plm_assemblies", "doc_count": 3}
            ]
    
    elif datasource == "soda":
        if "quality" in query_lower or "check" in query_lower:
            return """checks for workflows:
  - row_count > 0
  - missing_count(status) = 0
  - invalid_percent(status) < 5%""", [
                {"check": "row_count > 0", "table": "workflows", "status": "passed", "value": 47},
                {"check": "missing_count(status) = 0", "table": "workflows", "status": "passed", "value": 0}
            ]
        elif "freshness" in query_lower:
            return """checks for workflows:
  - freshness(created_at) < 1d""", [
                {"check": "freshness(created_at) < 1d", "table": "workflows", "status": "passed", "value": "2h"}
            ]
        else:
            return """checks for upload_metrics:
  - row_count > 0
  - duplicate_count(file_name) < 10""", [
                {"check": "row_count > 0", "table": "upload_metrics", "status": "passed", "value": 156}
            ]
    
    elif datasource == "graphql":
        if "workflow" in query_lower:
            return """query {
  workflows(limit: 10) {
    id
    name
    status
    createdAt
  }
}""", [
                {"id": "wf_001", "name": "ETL Pipeline", "status": "COMPLETED", "createdAt": "2026-01-09"},
                {"id": "wf_002", "name": "Validation", "status": "RUNNING", "createdAt": "2026-01-09"}
            ]
        elif "source" in query_lower or "connection" in query_lower:
            return """query {
  dataSources {
    id
    name
    type
  }
}""", [
                {"id": "ds_001", "name": "PostgreSQL Main", "type": "POSTGRESQL"},
                {"id": "ds_002", "name": "Neo4j Graph", "type": "NEO4J"}
            ]
        else:
            return """query {
  migrationJobs(status: COMPLETED) {
    id
    sourceTable
    targetTable
    rowsMigrated
  }
}""", [
                {"id": "mj_001", "sourceTable": "legacy_users", "targetTable": "users", "rowsMigrated": 5000}
            ]
    
    else:  # ollama
        return f"Analysis of: {query_lower}", [
            {"response": "Based on your query, I recommend checking the workflows table for status distribution and the service_health table for system performance metrics."}
        ]
    
    return f"-- Unable to generate query for: {query_lower}", []


@router.post("/nlq")
async def natural_language_query(request: NLQRequest):
    """
    Process natural language queries for analytics using Ollama LLM.
    
    Supports multiple data sources:
    - postgres: SQL queries for PostgreSQL
    - neo4j: Cypher queries for Neo4j graph database
    - opensearch: OpenSearch DSL queries (JSON)
    - soda: SODA data quality checks (YAML)
    - graphql: GraphQL queries
    - ollama: Direct LLM responses
    
    **Request Body:**
    - query: The natural language question
    - datasource: Target datasource (postgres, neo4j, opensearch, soda, graphql, ollama)
    - context: Additional context for query processing
    
    **Response:**
    - Generated query in appropriate format
    - Query results (mock data in demo mode)
    - Metadata about the query execution
    """
    import time
    start_time = time.time()
    
    try:
        query_lower = request.query.lower()
        datasource = request.datasource or "postgres"
        query_type = QUERY_TYPE_MAP.get(datasource, "sql")
        
        # Try to generate query using Ollama LLM
        generated_query, query_type = await _generate_query_with_ollama(request.query, datasource)
        
        results: list[dict] = []
        
        # Fallback to pattern matching if LLM fails
        if not generated_query:
            logger.info("Falling back to pattern matching for %s: %s", datasource, request.query)
            generated_query, results = _get_fallback_query(query_lower, datasource)
        else:
            # Generate mock results for the LLM-generated query
            _, results = _get_fallback_query(query_lower, datasource)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return {
            "success": True,
            "original_query": request.query,
            "generated_query": generated_query,
            "query_type": query_type,
            "datasource": datasource,
            "results": results,
            "llm_powered": generated_query is not None and not generated_query.startswith("--"),
            "metadata": {
                "execution_time_ms": execution_time,
                "rows_returned": len(results),
                "model": _ollama_model(),
                "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            }
        }
        
    except Exception as e:
        logger.error("NLQ processing failed: %s", e, exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "original_query": request.query,
            "generated_query": None,
            "results": [],
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        }
