"""
Excel and Power Query Database Adapter
Provides connectivity to Excel files and Power Query integration
"""

import pandas as pd  # type: ignore[import-untyped]
import openpyxl  # type: ignore[import-untyped]
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from ..database_adapters import DatabaseAdapter, DatabaseConnectionError, DatabaseQueryError

logger = logging.getLogger(__name__)

class ExcelAdapter(DatabaseAdapter):
    """Excel file adapter using pandas and openpyxl"""
    
    REQUIRED_PARAMS = ['file_path']
    OPTIONAL_PARAMS = ['sheet_name', 'header_row', 'skip_rows']
    DEFAULT_PORT = None
    DESCRIPTION = "Microsoft Excel files (.xlsx, .xls)"
    
    def __init__(self, connection_params: Dict[str, Any]):
        super().__init__(connection_params)
        self.file_path: Optional[Path] = None
        self.workbook: Any = None
        self.dataframes: Dict[str, Any] = {}

    async def _require_file_path(self) -> Path:
        if self.file_path is None:
            await self.connect()
        if self.file_path is None:
            raise DatabaseConnectionError("Excel file path is not initialized")
        return self.file_path
    
    async def connect(self) -> bool:
        """Open and validate Excel file"""
        try:
            self.file_path = Path(self.connection_params['file_path'])
            
            if not self.file_path.exists():
                raise FileNotFoundError(f"Excel file not found: {self.file_path}")
            
            # Check file extension
            if self.file_path.suffix.lower() not in ['.xlsx', '.xls', '.xlsm']:
                raise ValueError(f"Unsupported file format: {self.file_path.suffix}")
            
            # Try to open the file
            if self.file_path.suffix.lower() == '.xlsx':
                self.workbook = openpyxl.load_workbook(self.file_path, read_only=True)
            
            # Load all sheets into dataframes
            excel_file = pd.ExcelFile(self.file_path)
            for sheet_name in excel_file.sheet_names:
                try:
                    df = pd.read_excel(
                        self.file_path, 
                        sheet_name=sheet_name,
                        header=self.connection_params.get('header_row', 0),
                        skiprows=self.connection_params.get('skip_rows', 0)
                    )
                    self.dataframes[sheet_name] = df
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning("Could not load sheet '%s': %s", sheet_name, e)
            
            self.is_connected = True
            logger.info("Connected to Excel file: %s", self.file_path)
            return True
            
        except Exception as e:  # pylint: disable=broad-except
            self.is_connected = False
            logger.error("Excel connection failed: %s", e)
            raise DatabaseConnectionError(f"Failed to connect to Excel file: {e}") from e
    
    async def disconnect(self) -> None:
        """Close Excel file"""
        if self.workbook:
            self.workbook.close()
            self.workbook = None
        self.dataframes.clear()
        self.is_connected = False
        logger.info("Excel file closed")
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Excel file connection"""
        try:
            if not self.is_connected:
                await self.connect()

            file_path = await self._require_file_path()
            file_stats = file_path.stat()
            sheet_info = {}
            
            for sheet_name, df in self.dataframes.items():
                sheet_info[sheet_name] = {
                    "rows": len(df),
                    "columns": len(df.columns),
                    "column_names": list(df.columns)
                }
            
            return {
                "success": True,
                "message": "Excel file connection successful",
                "details": {
                    "file_path": str(file_path),
                    "file_size": file_stats.st_size,
                    "sheets": sheet_info,
                    "total_sheets": len(self.dataframes)
                }
            }
        except Exception as e:  # pylint: disable=broad-except
            return {
                "success": False,
                "message": f"Excel connection failed: {str(e)}",
                "details": {"error": str(e)}
            }
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a pandas query on Excel data"""
        try:
            if not self.is_connected:
                await self.connect()
            
            # Simple query parsing for Excel data
            # This is a basic implementation - could be extended with SQL-like queries
            sheet_name = params.get('sheet_name') if params else None
            
            if not sheet_name:
                # Use first sheet if none specified
                sheet_name = list(self.dataframes.keys())[0] if self.dataframes else None
            
            if not sheet_name or sheet_name not in self.dataframes:
                raise ValueError(f"Sheet '{sheet_name}' not found")
            
            df = self.dataframes[sheet_name]
            
            # Apply basic filtering if provided
            if params and 'filter' in params:
                filter_expr = params['filter']
                df = df.query(filter_expr)
            
            # Apply row limit if provided
            if params and 'limit' in params:
                limit = int(params['limit'])
                df = df.head(limit)
            
            # Convert to list of dictionaries
            return df.to_dict('records')
                
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Excel query error: %s", e)
            raise DatabaseQueryError(f"Query execution failed: {e}") from e
    
    async def get_tables(self) -> List[str]:
        """Get list of sheets (treated as tables)"""
        try:
            if not self.is_connected:
                await self.connect()
            return list(self.dataframes.keys())
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting Excel sheets: %s", e)
            return []
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific sheet"""
        try:
            if not self.is_connected:
                await self.connect()

            sheet_name = table_name
            
            if sheet_name not in self.dataframes:
                return {"sheet_name": sheet_name, "error": "Sheet not found"}
            
            df = self.dataframes[sheet_name]
            
            columns = []
            for col in df.columns:
                col_info = {
                    "name": str(col),
                    "type": str(df[col].dtype),
                    "non_null_count": int(df[col].notna().sum()),
                    "null_count": int(df[col].isna().sum()),
                    "unique_count": int(df[col].nunique())
                }
                
                # Add sample values for better understanding
                if not df[col].empty:
                    col_info["sample_values"] = df[col].dropna().head(3).tolist()
                
                columns.append(col_info)
            
            return {
                "sheet_name": sheet_name,
                "columns": columns,
                "column_count": len(columns),
                "row_count": len(df),
                "memory_usage": df.memory_usage(deep=True).sum()
            }
            
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting Excel sheet schema for %s: %s", sheet_name, e)
            return {
                "sheet_name": sheet_name,
                "columns": [],
                "error": str(e)
            }
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get comprehensive Excel file schema information"""
        try:
            if not self.is_connected:
                await self.connect()

            file_path = await self._require_file_path()
            file_stats = file_path.stat()
            sheets = await self.get_tables()

            sheets_schema: Dict[str, Any] = {}
            schema: Dict[str, Any] = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_size": file_stats.st_size,
                "file_type": "Excel",
                "sheets": sheets_schema,
                "total_sheets": len(sheets),
                "connection_info": await self.get_connection_info()
            }
            
            # Get detailed sheet schemas
            for sheet in sheets:
                sheet_schema = await self.get_table_schema(sheet)
                sheets_schema[sheet] = sheet_schema
            
            return schema
            
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error getting Excel schema: %s", e)
            raise DatabaseQueryError(f"Schema retrieval failed: {e}") from e

class PowerQueryAdapter(DatabaseAdapter):
    """Power Query adapter (placeholder for future implementation)"""
    
    REQUIRED_PARAMS = ['connection_string']
    OPTIONAL_PARAMS = ['query_timeout', 'authentication_type']
    DEFAULT_PORT = None
    DESCRIPTION = "Microsoft Power Query integration (requires Power BI/Excel installation)"
    
    async def connect(self) -> bool:
        """Connect to Power Query data source"""
        # This would require Power BI/Excel COM objects or REST API
        raise NotImplementedError("Power Query integration requires additional implementation")
    
    async def disconnect(self) -> None:
        """Disconnect from Power Query"""
        return None
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Power Query connection"""
        return {
            "success": False,
            "message": "Power Query integration not yet implemented",
            "details": {
                "note": "This feature requires Power BI Desktop or Excel with Power Query installed"
            }
        }
    
    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute Power Query"""
        raise NotImplementedError("Power Query integration requires additional implementation")
    
    async def get_tables(self) -> List[str]:
        """Get Power Query tables"""
        return []
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get Power Query table schema"""
        return {"table_name": table_name, "error": "Not implemented"}
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get Power Query schema"""
        return {"error": "Power Query integration not yet implemented"}

# Register the adapters
from ..database_adapters import DatabaseAdapterFactory  # noqa: E402
DatabaseAdapterFactory.register_adapter('excel', ExcelAdapter)
DatabaseAdapterFactory.register_adapter('powerquery', PowerQueryAdapter)
