from fastapi import APIRouter, Depends, HTTPException, Query, Response
import neo4j
from datetime import datetime
from core.config import NEO4J_DATABASE
from .dependencies import get_driver

router = APIRouter(prefix="/api")

@router.get("/health", summary="Health check endpoint")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "service": "Neo4j GraphTrace API"}

@router.get("/entities", summary="Get all node labels and relationship types with properties")
async def get_entities(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    driver_instance: neo4j.AsyncDriver = Depends(get_driver),
):
    entities = []
    try:
        # Prefer schema procedures to avoid N+1 queries (can be very slow on large graphs).
        try:
            node_result = await driver_instance.execute_query(
                """
                CALL db.schema.nodeTypeProperties()
                YIELD nodeType, propertyName
                WITH split(substring(nodeType, 1), ':') AS labels, propertyName
                UNWIND labels AS label
                WITH label, collect(DISTINCT propertyName) AS props
                RETURN label, props
                ORDER BY label
                """,
                database_=NEO4J_DATABASE,
            )
            for record in node_result.records:
                label = record[0] if len(record) else None
                if not label:
                    continue
                props = record[1] if len(record) > 1 and record[1] is not None else []
                entities.append({"type": "node", "label": label, "properties": props})

            rel_result = await driver_instance.execute_query(
                """
                CALL db.schema.relTypeProperties()
                YIELD relType, propertyName
                WITH relType, collect(DISTINCT propertyName) AS props
                RETURN relType AS label, props
                ORDER BY label
                """,
                database_=NEO4J_DATABASE,
            )
            for record in rel_result.records:
                rel_type = record[0] if len(record) else None
                if not rel_type:
                    continue
                props = record[1] if len(record) > 1 and record[1] is not None else []
                entities.append({"type": "relationship", "label": rel_type, "properties": props})
        except neo4j.exceptions.ClientError:
            # Fallback for older Neo4j editions/versions where schema procedures are unavailable.
            # We still return a consistent shape, but without enumerating properties.
            results = await driver_instance.execute_query("CALL db.labels()", database_=NEO4J_DATABASE)
            for record in results.records:
                label = record[0] if len(record) else None
                if label:
                    entities.append({"type": "node", "label": label, "properties": []})

            rel_results = await driver_instance.execute_query("CALL db.relationshipTypes()", database_=NEO4J_DATABASE)
            for record in rel_results.records:
                rel_type = record[0] if len(record) else None
                if rel_type:
                    entities.append({"type": "relationship", "label": rel_type, "properties": []})

        response.headers["X-Total-Count"] = str(len(entities))
        return entities[skip : skip + limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
