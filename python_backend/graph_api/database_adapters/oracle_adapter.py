"""
Oracle Database Adapter
Provides connectivity to Oracle databases using oracledb
"""

import oracledb
import logging
from typing import Dict, List, Any, Optional
from ..database_adapters import SQLDatabaseAdapter, DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger(__name__)

class OracleAdapter(SQLDatabaseAdapter):
    """Oracle database adapter using oracledb"""
    
    REQUIRED_PARAMS = ['host', 'service_name', 'username', 'password']
    OPTIONAL_PARAMS = ['port', 'sid', 'wallet_location', 'wallet_password']
    DEFAULT_PORT = 1521
    DESCRIPTION = "Oracle Database (on-premise and cloud)"
    
    def __init__(self, connection_params: Dict[str, Any]):
        super().__init__(connection_params)
        self.connection_pool = None
    
    def _build_dsn(self) -> str:
        """Build Oracle DSN string"""
        host = self.connection_params['host']
        port = self.connection_params.get('port', self.DEFAULT_PORT)
        
        if 'service_name' in self.connection_params:
            service_name = self.connection_params['service_name']
            return f"{host}:{port}/{service_name}"
        elif 'sid' in self.connection_params:
            sid = self.connection_params['sid']
            return f"{host}:{port}:{sid}"
        else:
            raise ValueError("Either 'service_name' or 'sid' must be provided")
    
    async def connect(self) -> bool:
        """Establish connection pool to Oracle"""
        try:
            dsn = self._build_dsn()
            username = self.connection_params['username']
            password = self.connection_params['password']
            
            # Check for wallet configuration (Oracle Cloud)
            if 'wallet_location' in self.connection_params:
                wallet_location = self.connection_params['wallet_location']
                wallet_password = self.connection_params.get('wallet_password', '')
                oracledb.init_oracle_client(config_dir=wallet_location)
            
            # Create connection pool
            self.connection_pool = oracledb.create_pool(
                user=username,
                password=password,
                dsn=dsn,
                min=1,
                max=10,
                increment=1
            )
            
            # Test the connection
            with self.connection_pool.acquire() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM DUAL')
                cursor.close()
            
            self.is_connected = True
            logger.info(f"Connected to Oracle: {self.connection_params['host']}")
            return True
            
        except Exception as e:
            self.is_connected = False
            logger.error(f"Oracle connection failed: {e}")
            raise DatabaseConnectionError(f"Failed to connect to Oracle: {e}")
    
    async def disconnect(self) -> None:
        """Close the connection pool"""
        if self.connection_pool:
            self.connection_pool.close()
            self.connection_pool = None
            self.is_connected = False
            logger.info("Oracle connection closed")
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Oracle connection"""
        try:
            if not self.is_connected:
                await self.connect()
            
            with self.connection_pool.acquire() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT BANNER FROM V$VERSION WHERE ROWNUM = 1")
                version = cursor.fetchone()[0]
                
                cursor.execute("SELECT SYS_CONTEXT('USERENV', 'DB_NAME') FROM DUAL")
                database = cursor.fetchone()[0]
                cursor.close()
            
            return {
                "success": True,
                "message": "Oracle connection successful",
                "details": {
                    "database": database,
                    "version": version,
                    "host": self.connection_params['host'],
                    "port": self.connection_params.get('port', self.DEFAULT_PORT)
                }
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Oracle connection failed: {str(e)}",
                "details": {"error": str(e)}
            }
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results"""
        try:
            if not self.is_connected:
                await self.connect()
            
            with self.connection_pool.acquire() as conn:
                cursor = conn.cursor()
                
                if params:
                    cursor.execute(query, list(params.values()))
                else:
                    cursor.execute(query)
                
                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # Fetch all rows
                rows = cursor.fetchall()
                
                # Convert to dictionaries
                results = []
                for row in rows:
                    row_dict = {}
                    for i, column in enumerate(columns):
                        row_dict[column] = row[i]
                    results.append(row_dict)
                
                cursor.close()
                
            return results
                
        except Exception as e:
            logger.error(f"Oracle query error: {e}")
            raise DatabaseQueryError(f"Query execution failed: {e}")
    
    async def get_tables(self) -> List[str]:
        """Get list of tables in the database"""
        query = """
        SELECT TABLE_NAME 
        FROM USER_TABLES 
        ORDER BY TABLE_NAME
        """
        try:
            results = await self.execute_query(query)
            return [row['TABLE_NAME'] for row in results]
        except Exception as e:
            logger.error(f"Error getting Oracle tables: {e}")
            return []
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific table"""
        query = """
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            NULLABLE,
            DATA_DEFAULT,
            DATA_LENGTH,
            DATA_PRECISION,
            DATA_SCALE
        FROM USER_TAB_COLUMNS 
        WHERE TABLE_NAME = :table_name
        ORDER BY COLUMN_ID
        """
        try:
            results = await self.execute_query(query, {'table_name': table_name.upper()})
            
            columns = []
            for row in results:
                columns.append({
                    "name": row['COLUMN_NAME'],
                    "type": row['DATA_TYPE'],
                    "nullable": row['NULLABLE'] == 'Y',
                    "default": row['DATA_DEFAULT'],
                    "length": row['DATA_LENGTH'],
                    "precision": row['DATA_PRECISION'],
                    "scale": row['DATA_SCALE']
                })
            
            # Get table size information
            size_query = """
            SELECT 
                NUM_ROWS,
                BLOCKS,
                AVG_ROW_LEN
            FROM USER_TABLES 
            WHERE TABLE_NAME = :table_name
            """
            size_results = await self.execute_query(size_query, {'table_name': table_name.upper()})
            size_info = size_results[0] if size_results else {}
            
            return {
                "table_name": table_name,
                "columns": columns,
                "column_count": len(columns),
                "num_rows": size_info.get('NUM_ROWS'),
                "blocks": size_info.get('BLOCKS'),
                "avg_row_length": size_info.get('AVG_ROW_LEN')
            }
            
        except Exception as e:
            logger.error(f"Error getting Oracle table schema for {table_name}: {e}")
            return {
                "table_name": table_name,
                "columns": [],
                "error": str(e)
            }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get comprehensive database schema information"""
        try:
            # Get basic database info
            with self.connection_pool.acquire() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT SYS_CONTEXT('USERENV', 'DB_NAME') FROM DUAL")
                database_name = cursor.fetchone()[0]
                
                cursor.execute("SELECT USER FROM DUAL")
                current_user = cursor.fetchone()[0]
                
                cursor.execute("SELECT BANNER FROM V$VERSION WHERE ROWNUM = 1")
                version = cursor.fetchone()[0]
                
                cursor.close()
            
            # Get table information
            tables = await self.get_tables()
            
            schema = {
                "database_name": database_name,
                "database_type": "Oracle",
                "version": version,
                "current_user": current_user,
                "tables": {},
                "total_tables": len(tables),
                "connection_info": await self.get_connection_info()
            }
            
            # Get detailed table schemas (limit to first 10 for performance)
            for table in tables[:10]:
                table_schema = await self.get_table_schema(table)
                schema["tables"][table] = table_schema
            
            if len(tables) > 10:
                schema["note"] = f"Showing first 10 tables out of {len(tables)} total tables"
            
            return schema
            
        except Exception as e:
            logger.error(f"Error getting Oracle schema: {e}")
            raise DatabaseQueryError(f"Schema retrieval failed: {e}")

# Register the adapter
from ..database_adapters import DatabaseAdapterFactory
DatabaseAdapterFactory.register_adapter('oracle', OracleAdapter)
