"""
Database Migration Service

Handles migration of data between different RDBMS sources using ETL orchestrator agent.
Supports: PostgreSQL, MySQL, SQL Server, Oracle → PostgreSQL/Neo4j/OpenSearch

Architecture:
- Extract: Connect to source RDBMS and query data
- Transform: Apply schema mapping and data validation
- Load: Insert into target database with quality checks
- Track: Record lineage in Neo4j graph
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class DatabaseMigrationService:
    """Service for orchestrating database-to-database migrations."""
    
    def __init__(self, db_session):
        self.db = db_session
        self.migration_stats = {}
    
    async def migrate_from_sqlserver(
        self,
        source_config: Dict[str, Any],
        target_config: Dict[str, Any],
        table_mappings: List[Dict[str, str]],
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Migrate data from SQL Server to target database.
        
        Args:
            source_config: SQL Server connection config
            target_config: Target database connection config
            table_mappings: List of {source_table, target_table, query}
            batch_size: Number of rows per batch
            
        Returns:
            Migration result with statistics
        """
        import pyodbc
        from sqlalchemy import create_engine
        
        migration_id = f"mig_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        results = {
            "migration_id": migration_id,
            "source_type": "sqlserver",
            "target_type": target_config.get("type", "postgres"),
            "started_at": datetime.utcnow().isoformat(),
            "tables_migrated": [],
            "total_rows": 0,
            "total_errors": 0
        }
        
        # Source connection (SQL Server)
        source_conn_str = self._build_sqlserver_connection_string(source_config)
        
        # Target connection (PostgreSQL)
        target_engine = create_engine(target_config["connection_string"])
        
        try:
            with pyodbc.connect(source_conn_str) as source_conn:
                for mapping in table_mappings:
                    source_table = mapping["source_table"]
                    target_table = mapping["target_table"]
                    query = mapping.get("query") or f"SELECT * FROM {source_table}"
                    transform_fn = mapping.get("transform")
                    
                    logger.info(f"Migrating {source_table} → {target_table}")
                    
                    table_result = await self._migrate_table(
                        source_conn=source_conn,
                        target_engine=target_engine,
                        source_query=query,
                        target_table=target_table,
                        transform_fn=transform_fn,
                        batch_size=batch_size,
                        migration_id=migration_id
                    )
                    
                    results["tables_migrated"].append(table_result)
                    results["total_rows"] += table_result["rows_migrated"]
                    results["total_errors"] += table_result["errors"]
        
        finally:
            target_engine.dispose()
        
        results["completed_at"] = datetime.utcnow().isoformat()
        results["status"] = "success" if results["total_errors"] == 0 else "partial_failure"
        
        # Record in Neo4j lineage graph
        await self._record_migration_lineage(results)
        
        return results
    
    async def migrate_from_oracle(
        self,
        source_config: Dict[str, Any],
        target_config: Dict[str, Any],
        table_mappings: List[Dict[str, str]],
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Migrate data from Oracle to target database.
        
        Similar to SQL Server migration but uses oracledb driver.
        """
        import oracledb
        from sqlalchemy import create_engine
        
        migration_id = f"mig_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        results = {
            "migration_id": migration_id,
            "source_type": "oracle",
            "target_type": target_config.get("type", "postgres"),
            "started_at": datetime.utcnow().isoformat(),
            "tables_migrated": [],
            "total_rows": 0,
            "total_errors": 0
        }
        
        # Source connection (Oracle)
        dsn = f"{source_config['host']}:{source_config['port']}/{source_config['service_name']}"
        
        # Target connection
        target_engine = create_engine(target_config["connection_string"])
        
        try:
            with oracledb.connect(
                user=source_config["username"],
                password=source_config["password"],
                dsn=dsn
            ) as source_conn:
                for mapping in table_mappings:
                    source_table = mapping["source_table"]
                    target_table = mapping["target_table"]
                    query = mapping.get("query") or f"SELECT * FROM {source_table}"
                    transform_fn = mapping.get("transform")
                    
                    logger.info(f"Migrating Oracle {source_table} → {target_table}")
                    
                    table_result = await self._migrate_table_oracle(
                        source_conn=source_conn,
                        target_engine=target_engine,
                        source_query=query,
                        target_table=target_table,
                        transform_fn=transform_fn,
                        batch_size=batch_size,
                        migration_id=migration_id
                    )
                    
                    results["tables_migrated"].append(table_result)
                    results["total_rows"] += table_result["rows_migrated"]
                    results["total_errors"] += table_result["errors"]
        
        finally:
            target_engine.dispose()
        
        results["completed_at"] = datetime.utcnow().isoformat()
        results["status"] = "success" if results["total_errors"] == 0 else "partial_failure"
        
        await self._record_migration_lineage(results)
        
        return results
    
    async def _migrate_table(
        self,
        source_conn: Any,
        target_engine: Any,
        source_query: str,
        target_table: str,
        transform_fn: Optional[callable],
        batch_size: int,
        migration_id: str
    ) -> Dict[str, Any]:
        """Migrate a single table from source to target."""
        import pandas as pd
        
        table_stats = {
            "table": target_table,
            "rows_migrated": 0,
            "errors": 0,
            "batches": 0
        }
        
        try:
            # Fetch data in batches
            with source_conn.cursor() as cursor:
                cursor.execute(source_query)
                columns = [desc[0] for desc in cursor.description]
                
                while True:
                    rows = cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(rows, columns=columns)
                    
                    # Apply transformations if provided
                    if transform_fn:
                        df = transform_fn(df)
                    
                    # Add migration metadata
                    df["_migration_id"] = migration_id
                    df["_migrated_at"] = datetime.utcnow()
                    
                    # Insert into target
                    try:
                        df.to_sql(
                            target_table,
                            target_engine,
                            if_exists="append",
                            index=False,
                            method="multi"
                        )
                        table_stats["rows_migrated"] += len(df)
                        table_stats["batches"] += 1
                    
                    except Exception as e:
                        logger.error(f"Batch insert failed: {e}")
                        table_stats["errors"] += len(df)
        
        except Exception as e:
            logger.error(f"Table migration failed: {e}")
            table_stats["error_message"] = str(e)
        
        return table_stats
    
    async def _migrate_table_oracle(
        self,
        source_conn: Any,
        target_engine: Any,
        source_query: str,
        target_table: str,
        transform_fn: Optional[callable],
        batch_size: int,
        migration_id: str
    ) -> Dict[str, Any]:
        """Migrate from Oracle, handling Oracle-specific data types."""
        import pandas as pd
        
        table_stats = {
            "table": target_table,
            "rows_migrated": 0,
            "errors": 0,
            "batches": 0
        }
        
        try:
            with source_conn.cursor() as cursor:
                cursor.execute(source_query)
                columns = [desc[0] for desc in cursor.description]
                
                while True:
                    rows = cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    
                    # Handle Oracle-specific types (LOBs, TIMESTAMP, etc.)
                    cleaned_rows = []
                    for row in rows:
                        cleaned_row = []
                        for val in row:
                            # Convert LOB objects
                            if hasattr(val, 'read'):
                                cleaned_row.append(val.read() if val else None)
                            else:
                                cleaned_row.append(val)
                        cleaned_rows.append(cleaned_row)
                    
                    df = pd.DataFrame(cleaned_rows, columns=columns)
                    
                    if transform_fn:
                        df = transform_fn(df)
                    
                    df["_migration_id"] = migration_id
                    df["_migrated_at"] = datetime.utcnow()
                    
                    try:
                        df.to_sql(
                            target_table,
                            target_engine,
                            if_exists="append",
                            index=False,
                            method="multi"
                        )
                        table_stats["rows_migrated"] += len(df)
                        table_stats["batches"] += 1
                    
                    except Exception as e:
                        logger.error(f"Oracle batch insert failed: {e}")
                        table_stats["errors"] += len(df)
        
        except Exception as e:
            logger.error(f"Oracle table migration failed: {e}")
            table_stats["error_message"] = str(e)
        
        return table_stats
    
    async def _record_migration_lineage(self, migration_result: Dict[str, Any]) -> None:
        """Record migration lineage in Neo4j graph for traceability."""
        try:
            from services.neo4j_graphrag_service import Neo4jGraphRAGService
            import os
            
            neo4j_service = Neo4jGraphRAGService(
                uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                username=os.getenv("NEO4J_USER", "neo4j"),
                password=os.getenv("NEO4J_PASSWORD", "")
            )
            
            # Create migration node
            migration_node_query = """
            CREATE (m:Migration {
                migration_id: $migration_id,
                source_type: $source_type,
                target_type: $target_type,
                started_at: datetime($started_at),
                completed_at: datetime($completed_at),
                status: $status,
                total_rows: $total_rows,
                total_errors: $total_errors
            })
            RETURN m
            """
            
            await neo4j_service.execute_cypher(migration_node_query, migration_result)
            
            # Create table lineage relationships
            for table in migration_result["tables_migrated"]:
                lineage_query = """
                MATCH (m:Migration {migration_id: $migration_id})
                MERGE (t:Table {name: $table_name})
                CREATE (m)-[:MIGRATED_TABLE {
                    rows: $rows,
                    errors: $errors,
                    batches: $batches
                }]->(t)
                """
                
                await neo4j_service.execute_cypher(lineage_query, {
                    "migration_id": migration_result["migration_id"],
                    "table_name": table["table"],
                    "rows": table["rows_migrated"],
                    "errors": table["errors"],
                    "batches": table["batches"]
                })
            
            logger.info(f"Migration lineage recorded: {migration_result['migration_id']}")
        
        except Exception as e:
            logger.warning(f"Failed to record migration lineage: {e}")
    
    def _build_sqlserver_connection_string(self, config: Dict[str, Any]) -> str:
        """Build SQL Server ODBC connection string."""
        driver = config.get("driver", "{ODBC Driver 17 for SQL Server}")
        return (
            f"DRIVER={driver};"
            f"SERVER={config['host']},{config.get('port', 1433)};"
            f"DATABASE={config['database']};"
            f"UID={config['username']};"
            f"PWD={config['password']};"
            "TrustServerCertificate=yes;"
        )
    
    async def validate_migration(
        self,
        migration_id: str,
        source_count_queries: Dict[str, str],
        target_count_queries: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Validate migration by comparing row counts and data integrity.
        
        Returns:
            Validation report with discrepancies
        """
        validation_result = {
            "migration_id": migration_id,
            "validated_at": datetime.utcnow().isoformat(),
            "tables": [],
            "overall_status": "pass"
        }
        
        for table_name in source_count_queries.keys():
            source_query = source_count_queries[table_name]
            target_query = target_count_queries.get(table_name)
            
            if not target_query:
                continue
            
            # Execute count queries (implementation depends on connection management)
            # This is a placeholder for the validation logic
            table_validation = {
                "table": table_name,
                "source_count": 0,  # Execute source_query
                "target_count": 0,  # Execute target_query
                "match": False,
                "discrepancy": 0
            }
            
            validation_result["tables"].append(table_validation)
            
            if not table_validation["match"]:
                validation_result["overall_status"] = "failed"
        
        return validation_result
