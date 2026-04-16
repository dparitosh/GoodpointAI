"""
PostgreSQL Database Adapter
Provides connectivity to PostgreSQL databases using asyncpg
"""

import asyncpg  # type: ignore[import-untyped]
import logging
from typing import Dict, List, Any, Optional
from ..database_adapters import SQLDatabaseAdapter, DatabaseConnectionError, DatabaseQueryError
from core.db_session import DATABASE_URL
from core.postgres_config import asyncpg_params_from_database_url, is_postgres_database_url

logger = logging.getLogger(__name__)

class PostgreSQLAdapter(SQLDatabaseAdapter):
    """PostgreSQL database adapter using asyncpg"""
    
    REQUIRED_PARAMS = ['host', 'database', 'username', 'password']
    OPTIONAL_PARAMS = ['port', 'schema', 'ssl_mode']
    DEFAULT_PORT = 5432
    DESCRIPTION = "PostgreSQL relational database"
    
    def __init__(self, connection_params: Dict[str, Any]):
        super().__init__(connection_params)
        self.pool: Any = None

    async def _require_pool(self) -> Any:
        if not self.is_connected or self.pool is None:
            await self.connect()
        if self.pool is None:
            raise DatabaseConnectionError("PostgreSQL connection pool is not initialized")
        return self.pool
    
    async def connect(self) -> bool:
        """Establish connection pool to PostgreSQL"""
        try:
            # Allow a single-source-of-truth DATABASE_URL to drive asyncpg.
            if "database_url" in self.connection_params and str(self.connection_params.get("database_url") or "").strip():
                params = asyncpg_params_from_database_url(str(self.connection_params["database_url"]).strip())
                host = params["host"]
                port = params["port"]
                database = params["database"]
                username = params["user"]
                password = params["password"]
            elif is_postgres_database_url(DATABASE_URL):
                params = asyncpg_params_from_database_url(DATABASE_URL)
                host = params["host"]
                port = params["port"]
                database = params["database"]
                username = params["user"]
                password = params["password"]
            else:
                # Legacy param form
                host = self.connection_params['host']
                port = self.connection_params.get('port', self.DEFAULT_PORT)
                database = self.connection_params['database']
                username = self.connection_params['username']
                password = self.connection_params['password']
            
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                host=host,
                port=port,
                database=database,
                user=username,
                password=password,
                min_size=1,
                max_size=10
            )
            
            # Test the connection
            async with self.pool.acquire() as conn:
                await conn.execute('SELECT 1')
            
            self.is_connected = True
            logger.info("Connected to PostgreSQL: %s:%s/%s", host, port, database)
            return True
            
        except Exception as e:  # pylint: disable=broad-except
            self.is_connected = False
            logger.error("PostgreSQL connection failed: %s", e)
            raise DatabaseConnectionError(f"Failed to connect to PostgreSQL: {e}") from e
    
    async def disconnect(self) -> None:
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self.is_connected = False
            logger.info("PostgreSQL connection closed")
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test PostgreSQL connection"""
        try:
            pool = await self._require_pool()
            async with pool.acquire() as conn:
                result = await conn.fetchrow('SELECT version() as version, current_database() as database')
                
            return {
                "success": True,
                "message": "PostgreSQL connection successful",
                "details": {
                    "database": result['database'],
                    "version": result['version'],
                    "host": self.connection_params['host'],
                    "port": self.connection_params.get('port', self.DEFAULT_PORT)
                }
            }
        except Exception as e:  # pylint: disable=broad-except
            return {
                "success": False,
                "message": f"PostgreSQL connection failed: {str(e)}",
                "details": {"error": str(e)}
            }
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results"""
        try:
            pool = await self._require_pool()
            async with pool.acquire() as conn:
                if params:
                    rows = await conn.fetch(query, *params.values())
                else:
                    rows = await conn.fetch(query)
                
                # Convert records to dictionaries
                return [dict(row) for row in rows]
                
        except Exception as e:  # pylint: disable=broad-except
            logger.error("PostgreSQL query error: %s", e)
            raise DatabaseQueryError(f"Query execution failed: {e}") from e
    
    async def get_tables(self) -> List[str]:
        """Get list of tables in the database"""
        query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
        try:
            results = await self.execute_query(query)
            return [row['table_name'] for row in results]
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting PostgreSQL tables: %s", e)
            return []
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific table"""
        query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns 
        WHERE table_name = $1 
        AND table_schema = 'public'
        ORDER BY ordinal_position
        """
        try:
            pool = await self._require_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, table_name)
            
            columns = []
            for row in rows:
                columns.append({
                    "name": row['column_name'],
                    "type": row['data_type'],
                    "nullable": row['is_nullable'] == 'YES',
                    "default": row['column_default'],
                    "max_length": row['character_maximum_length'],
                    "precision": row['numeric_precision'],
                    "scale": row['numeric_scale']
                })
            
            # Get table size information
            size_query = """
            SELECT 
                pg_size_pretty(pg_total_relation_size($1)) as total_size,
                pg_size_pretty(pg_relation_size($1)) as table_size
            """
            async with pool.acquire() as conn:
                size_result = await conn.fetchrow(size_query, table_name)
            
            return {
                "table_name": table_name,
                "columns": columns,
                "column_count": len(columns),
                "total_size": size_result['total_size'] if size_result else 'Unknown',
                "table_size": size_result['table_size'] if size_result else 'Unknown'
            }
            
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting PostgreSQL table schema for %s: %s", table_name, e)
            return {
                "table_name": table_name,
                "columns": [],
                "error": str(e)
            }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get comprehensive database schema information"""
        try:
            # Get basic database info
            info_query = """
            SELECT 
                current_database() as database_name,
                current_user as current_user,
                version() as version
            """
            pool = await self._require_pool()
            async with pool.acquire() as conn:
                db_info = await conn.fetchrow(info_query)
            
            # Get table information
            tables = await self.get_tables()
            
            schema = {
                "database_name": db_info['database_name'],
                "database_type": "PostgreSQL",
                "version": db_info['version'],
                "current_user": db_info['current_user'],
                "tables": {},
                "total_tables": len(tables),
                "connection_info": await self.get_connection_info()
            }
            
            # Get detailed table schemas
            for table in tables[:10]:  # Limit to first 10 tables for performance
                table_schema = await self.get_table_schema(table)
                schema["tables"][table] = table_schema
            
            if len(tables) > 10:
                schema["note"] = f"Showing first 10 tables out of {len(tables)} total tables"
            
            return schema
            
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting PostgreSQL schema: %s", e)
            raise DatabaseQueryError(f"Schema retrieval failed: {e}") from e

# Register the adapter
from ..database_adapters import DatabaseAdapterFactory  # noqa: E402
DatabaseAdapterFactory.register_adapter('postgresql', PostgreSQLAdapter)
