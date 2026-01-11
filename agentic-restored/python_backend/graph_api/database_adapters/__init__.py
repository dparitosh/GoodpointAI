"""
Database Adapter Factory and Base Classes
Provides a unified interface for connecting to different database types
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseAdapter(ABC):
    """Base class for all database adapters"""
    
    def __init__(self, connection_params: Dict[str, Any]):
        self.connection_params = connection_params
        self.connection = None
        self.is_connected = False
        
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the database"""
        raise NotImplementedError
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close the database connection"""
        raise NotImplementedError
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """Test the database connection and return status"""
        raise NotImplementedError
    
    @abstractmethod
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results"""
        raise NotImplementedError
    
    @abstractmethod
    async def get_schema(self) -> Dict[str, Any]:
        """Get database schema information"""
        raise NotImplementedError
    
    @abstractmethod
    async def get_tables(self) -> List[str]:
        """Get list of tables/collections"""
        raise NotImplementedError
    
    @abstractmethod
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific table"""
        raise NotImplementedError
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information and status"""
        return {
            "adapter_type": self.__class__.__name__,
            "is_connected": self.is_connected,
            "connection_params": {k: v for k, v in self.connection_params.items() if k != 'password'},
            "last_checked": datetime.now().isoformat()
        }

class DatabaseAdapterFactory:
    """Factory for creating database adapters"""
    
    _adapters: Dict[str, Any] = {}
    
    @classmethod
    def register_adapter(cls, db_type: str, adapter_class):
        """Register a new adapter type"""
        cls._adapters[db_type] = adapter_class
    
    @classmethod
    def create_adapter(cls, db_type: str, connection_params: Dict[str, Any]) -> DatabaseAdapter:
        """Create an adapter instance for the specified database type"""
        if db_type not in cls._adapters:
            raise ValueError(f"Unsupported database type: {db_type}")
        
        adapter_class = cls._adapters[db_type]
        return adapter_class(connection_params)
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """Get list of supported database types"""
        return list(cls._adapters.keys())
    
    @classmethod
    def get_adapter_info(cls, db_type: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific adapter type"""
        if db_type not in cls._adapters:
            return None
        
        adapter_class = cls._adapters[db_type]
        return {
            "type": db_type,
            "class_name": adapter_class.__name__,
            "required_params": getattr(adapter_class, 'REQUIRED_PARAMS', []),
            "optional_params": getattr(adapter_class, 'OPTIONAL_PARAMS', []),
            "default_port": getattr(adapter_class, 'DEFAULT_PORT', None),
            "description": getattr(adapter_class, 'DESCRIPTION', '')
        }

# Base SQL Adapter for relational databases
class SQLDatabaseAdapter(DatabaseAdapter):
    """Base class for SQL database adapters"""
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get database schema information"""
        try:
            tables = await self.get_tables()
            tables_schema: Dict[str, Any] = {}
            schema: Dict[str, Any] = {
                "database": self.connection_params.get('database'),
                "tables": tables_schema,
                "total_tables": len(tables)
            }
            
            for table in tables:
                table_schema = await self.get_table_schema(table)
                tables_schema[table] = table_schema
                
            return schema
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting schema: %s", e)
            raise
    
    async def execute_simple_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a simple query with error handling"""
        try:
            return await self.execute_query(query)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error executing query: %s", e)
            return []

# Exception classes
class DatabaseConnectionError(Exception):
    """Raised when database connection fails"""

class DatabaseQueryError(Exception):
    """Raised when database query fails"""

class UnsupportedDatabaseError(Exception):
    """Raised when trying to use an unsupported database type"""
