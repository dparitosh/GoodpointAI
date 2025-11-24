"""
PostgreSQL Database Adapter
Provides connectivity to PostgreSQL databases using asyncpg
"""

import asyncpg
import logging
from typing import Dict, List, Any, Optional
from ..database_adapters import SQLDatabaseAdapter, DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger(__name__)

class PostgreSQLAdapter(SQLDatabaseAdapter):
    """PostgreSQL database adapter using asyncpg"""
    
    REQUIRED_PARAMS = ['host', 'database', 'username', 'password']
    OPTIONAL_PARAMS = ['port', 'schema', 'ssl_mode']
    DEFAULT_PORT = 5432
    DESCRIPTION = "PostgreSQL relational database"
    
    def __init__(self, connection_params: Dict[str, Any]):
        super().__init__(connection_params)
        self.pool = None
    
    async def connect(self) -> bool:
        """Establish connection pool to PostgreSQL"""
        try:
            # Build connection string
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
            logger.info(f"Connected to PostgreSQL: {host}:{port}/{database}")
            return True
            
        except Exception as e:
            self.is_connected = False
            logger.error(f"PostgreSQL connection failed: {e}")
            raise DatabaseConnectionError(f"Failed to connect to PostgreSQL: {e}")
    
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
            if not self.is_connected:
                await self.connect()
            
            async with self.pool.acquire() as conn:
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
        except Exception as e:
            return {
                "success": False,
                "message": f"PostgreSQL connection failed: {str(e)}",
                "details": {"error": str(e)}
            }
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results"""
        try:
            if not self.is_connected:
                await self.connect()
            
            async with self.pool.acquire() as conn:
                if params:
                    rows = await conn.fetch(query, *params.values())
                else:
                    rows = await conn.fetch(query)
                
                # Convert records to dictionaries
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"PostgreSQL query error: {e}")
            raise DatabaseQueryError(f"Query execution failed: {e}")
    
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
        except Exception as e:
            logger.error(f"Error getting PostgreSQL tables: {e}")
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
            async with self.pool.acquire() as conn:
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
            async with self.pool.acquire() as conn:
                size_result = await conn.fetchrow(size_query, table_name)
            
            return {
                "table_name": table_name,
                "columns": columns,
                "column_count": len(columns),
                "total_size": size_result['total_size'] if size_result else 'Unknown',
                "table_size": size_result['table_size'] if size_result else 'Unknown'
            }
            
        except Exception as e:
            logger.error(f"Error getting PostgreSQL table schema for {table_name}: {e}")
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
            async with self.pool.acquire() as conn:
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
            
        except Exception as e:
            logger.error(f"Error getting PostgreSQL schema: {e}")
            raise DatabaseQueryError(f"Schema retrieval failed: {e}")

# Register the adapter
from ..database_adapters import DatabaseAdapterFactory
DatabaseAdapterFactory.register_adapter('postgresql', PostgreSQLAdapter)
