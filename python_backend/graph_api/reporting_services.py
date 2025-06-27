from fastapi import APIRouter, Depends, HTTPException
import neo4j
from datetime import datetime
from core.config import NEO4J_DATABASE
from .dependencies import get_driver

router = APIRouter(prefix="/api")

@router.get("/health", summary="Health check endpoint")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "service": "Neo4j GraphTrace API"}

@router.get("/entities", summary="Get all node labels and relationship types with properties")
async def get_entities(driver_instance: neo4j.AsyncDriver = Depends(get_driver)):
    entities = []
    try:
        # Node labels and properties
        results = await driver_instance.execute_query("CALL db.labels()", database_=NEO4J_DATABASE)
        for record in results.records:
            label = record[0] if len(record) else None
            if not label:
                continue
            prop_result = await driver_instance.execute_query(
                f"MATCH (n:`{label}`) UNWIND keys(n) AS k RETURN collect(DISTINCT k) AS props LIMIT 1",
                database_=NEO4J_DATABASE
            )
            props = []
            for prop_record in prop_result.records:
                props = prop_record[0] if len(prop_record) else []
            entities.append({"type": "node", "label": label, "properties": props})

        # Relationship types and properties
        rel_results = await driver_instance.execute_query("CALL db.relationshipTypes()", database_=NEO4J_DATABASE)
        for record in rel_results.records:
            rel_type = record[0] if len(record) else None
            if not rel_type:
                continue
            prop_result = await driver_instance.execute_query(
                f"MATCH ()-[r:`{rel_type}`]->() UNWIND keys(r) AS k RETURN collect(DISTINCT k) AS props LIMIT 1",
                database_=NEO4J_DATABASE
            )
            props = []
            for prop_record in prop_result.records:
                props = prop_record[0] if len(prop_record) else []
            entities.append({"type": "relationship", "label": rel_type, "properties": props})

        return entities
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
