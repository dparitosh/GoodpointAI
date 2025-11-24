"""
Microsoft SQL Server Database Adapter
Provides connectivity to SQL Server databases using pyodbc and pymssql
"""

import pyodbc
import logging
from typing import Dict, List, Any, Optional
from ..database_adapters import SQLDatabaseAdapter, DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger(__name__)

class SQLServerAdapter(SQLDatabaseAdapter):
    """SQL Server database adapter using pyodbc"""
    
    REQUIRED_PARAMS = ['host', 'database', 'username', 'password']
    OPTIONAL_PARAMS = ['port', 'driver', 'trusted_connection', 'encrypt']
    DEFAULT_PORT = 1433
    DESCRIPTION = "Microsoft SQL Server relational database"
    
    def __init__(self, connection_params: Dict[str, Any]):
        super().__init__(connection_params)
        self.connection_string = None
    
    def _build_connection_string(self) -> str:
        """Build SQL Server connection string"""
        host = self.connection_params['host']
        port = self.connection_params.get('port', self.DEFAULT_PORT)
        database = self.connection_params['database']
        username = self.connection_params['username']
        password = self.connection_params['password']
        driver = self.connection_params.get('driver', '{ODBC Driver 17 for SQL Server}')
        encrypt = self.connection_params.get('encrypt', 'yes')
        
        if self.connection_params.get('trusted_connection'):
            conn_str = f"DRIVER={driver};SERVER={host},{port};DATABASE={database};Trusted_Connection=yes;Encrypt={encrypt}"
        else:
            conn_str = f"DRIVER={driver};SERVER={host},{port};DATABASE={database};UID={username};PWD={password};Encrypt={encrypt}"
        
        return conn_str
    
    async def connect(self) -> bool:
        """Establish connection to SQL Server"""
        try:
            self.connection_string = self._build_connection_string()
            
            # Test the connection
            conn = pyodbc.connect(self.connection_string)
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.close()
            conn.close()
            
            self.is_connected = True
            logger.info(f"Connected to SQL Server: {self.connection_params['host']}")
            return True
            
        except Exception as e:
            self.is_connected = False
            logger.error(f"SQL Server connection failed: {e}")
            raise DatabaseConnectionError(f"Failed to connect to SQL Server: {e}")
    
    async def disconnect(self) -> None:
        """Close the database connection"""
        self.is_connected = False
        logger.info("SQL Server connection closed")
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test SQL Server connection"""
        try:
            if not self.is_connected:
                await self.connect()
            
            conn = pyodbc.connect(self.connection_string)
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION as version, DB_NAME() as database")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return {
                "success": True,
                "message": "SQL Server connection successful",
                "details": {
                    "database": result[1],
                    "version": result[0],
                    "host": self.connection_params['host'],
                    "port": self.connection_params.get('port', self.DEFAULT_PORT)
                }
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"SQL Server connection failed: {str(e)}",
                "details": {"error": str(e)}
            }
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results"""
        try:
            if not self.is_connected:
                await self.connect()
            
            conn = pyodbc.connect(self.connection_string)
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, list(params.values()))
            else:
                cursor.execute(query)
            
            # Get column names
            columns = [column[0] for column in cursor.description] if cursor.description else []
            
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
            conn.close()
            
            return results
                
        except Exception as e:
            logger.error(f"SQL Server query error: {e}")
            raise DatabaseQueryError(f"Query execution failed: {e}")
    
    async def get_tables(self) -> List[str]:
        """Get list of tables in the database"""
        query = """
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE' 
        ORDER BY TABLE_NAME
        """
        try:
            results = await self.execute_query(query)
            return [row['TABLE_NAME'] for row in results]
        except Exception as e:
            logger.error(f"Error getting SQL Server tables: {e}")
            return []
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific table"""
        query = """
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            CHARACTER_MAXIMUM_LENGTH,
            NUMERIC_PRECISION,
            NUMERIC_SCALE
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """
        try:
            results = await self.execute_query(query, {'table_name': table_name})
            
            columns = []
            for row in results:
                columns.append({
                    "name": row['COLUMN_NAME'],
                    "type": row['DATA_TYPE'],
                    "nullable": row['IS_NULLABLE'] == 'YES',
                    "default": row['COLUMN_DEFAULT'],
                    "max_length": row['CHARACTER_MAXIMUM_LENGTH'],
                    "precision": row['NUMERIC_PRECISION'],
                    "scale": row['NUMERIC_SCALE']
                })
            
            return {
                "table_name": table_name,
                "columns": columns,
                "column_count": len(columns)
            }
            
        except Exception as e:
            logger.error(f"Error getting SQL Server table schema for {table_name}: {e}")
            return {
                "table_name": table_name,
                "columns": [],
                "error": str(e)
            }

# Register the adapter
from ..database_adapters import DatabaseAdapterFactory
DatabaseAdapterFactory.register_adapter('mssql', SQLServerAdapter)
DatabaseAdapterFactory.register_adapter('sqlserver', SQLServerAdapter)
