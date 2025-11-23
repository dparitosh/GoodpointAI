"""
GraphQL Service - Core parsing, schema generation, and pseudo-GraphQL execution.
Supports XML and JSON schema introspection, query execution, and data transformations.
"""

import json
import xml.etree.ElementTree as ET
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime


class GraphQLService:
    """
    Service for GraphQL-like operations on XML/JSON data sources.
    Provides schema introspection, query execution, and transformation capabilities.
    """
    
    def __init__(self):
        self.cache = {}
    
    def parse_xml_to_dict(self, content: str) -> Dict[str, Any]:
        """
        Parse XML content to dictionary structure.
        
        Args:
            content: XML string content
            
        Returns:
            Dictionary representation of XML
            
        Raises:
            ValueError: If XML is invalid or malformed
        """
        try:
            root = ET.fromstring(content)
            return self._element_to_dict(root)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML format: {str(e)}")
    
    def _element_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary recursively."""
        result = {}
        
        # Add attributes
        if element.attrib:
            result["@attributes"] = dict(element.attrib)
        
        # Add text content
        if element.text and element.text.strip():
            if len(element) == 0:  # No children
                return element.text.strip()
            result["@text"] = element.text.strip()
        
        # Add children
        for child in element:
            child_data = self._element_to_dict(child)
            if child.tag in result:
                # Convert to list if multiple elements with same tag
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result if result else element.text
    
    def parse_json_to_dict(self, content: str) -> Dict[str, Any]:
        """
        Parse JSON content to dictionary structure.
        
        Args:
            content: JSON string content
            
        Returns:
            Dictionary representation of JSON
            
        Raises:
            ValueError: If JSON is invalid or malformed
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
    
    def introspect_schema(self, content: str, format: str, name: str) -> Dict[str, Any]:
        """
        Introspect schema from XML or JSON content.
        
        Args:
            content: Source content (XML or JSON string)
            format: Format type ('xml' or 'json')
            name: Schema name for identification
            
        Returns:
            SchemaIntrospectionResponse with fields and types mapping
            
        Raises:
            ValueError: If format is invalid or content cannot be parsed
        """
        if format not in ['xml', 'json']:
            raise ValueError(f"Invalid format: {format}. Must be 'xml' or 'json'")
        
        # Parse content based on format
        if format == 'xml':
            data = self.parse_xml_to_dict(content)
        else:
            data = self.parse_json_to_dict(content)
        
        # Generate schema hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Extract fields and types
        fields, types = self._extract_schema(data)
        
        return {
            "name": name,
            "format": format,
            "schema_hash": content_hash,
            "fields": fields,
            "types": types,
            "metadata": {
                "introspected_at": datetime.utcnow().isoformat(),
                "field_count": len(fields),
                "type_count": len(types)
            }
        }
    
    def _extract_schema(self, data: Any, path: str = "", fields: Dict = None, types: Dict = None) -> tuple:
        """
        Recursively extract field definitions and type information from data structure.
        
        Returns:
            Tuple of (fields dict, types dict)
        """
        if fields is None:
            fields = {}
        if types is None:
            types = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                if key.startswith('@'):
                    continue  # Skip attributes
                    
                field_path = f"{path}.{key}" if path else key
                value_type = self._infer_type(value)
                
                fields[field_path] = {
                    "type": value_type,
                    "nullable": value is None,
                    "description": f"Field {field_path}"
                }
                
                if value_type not in types:
                    types[value_type] = {
                        "name": value_type,
                        "kind": self._get_type_kind(value),
                        "fields": []
                    }
                
                # Recurse for nested structures
                if isinstance(value, (dict, list)):
                    self._extract_schema(value, field_path, fields, types)
        
        elif isinstance(data, list) and len(data) > 0:
            # Analyze first item for array type
            self._extract_schema(data[0], path, fields, types)
        
        return fields, types
    
    def _infer_type(self, value: Any) -> str:
        """Infer GraphQL-like type from Python value."""
        if value is None:
            return "Null"
        elif isinstance(value, bool):
            return "Boolean"
        elif isinstance(value, int):
            return "Int"
        elif isinstance(value, float):
            return "Float"
        elif isinstance(value, str):
            return "String"
        elif isinstance(value, list):
            if len(value) > 0:
                return f"[{self._infer_type(value[0])}]"
            return "[Any]"
        elif isinstance(value, dict):
            return "Object"
        else:
            return "Any"
    
    def _get_type_kind(self, value: Any) -> str:
        """Get GraphQL type kind."""
        if isinstance(value, list):
            return "LIST"
        elif isinstance(value, dict):
            return "OBJECT"
        else:
            return "SCALAR"
    
    def execute_query(self, query: str, data: Dict[str, Any], variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute pseudo-GraphQL query against JSON data.
        
        Args:
            query: GraphQL-like query string
            data: Source data dictionary
            variables: Optional query variables
            
        Returns:
            QueryResponse with data or errors
        """
        try:
            # Parse query to extract field selectors
            selectors = self._parse_query(query)
            
            # Execute selection
            result = self._select_fields(data, selectors)
            
            return {
                "data": result,
                "errors": []
            }
        except ValueError as e:
            return {
                "data": None,
                "errors": [{
                    "message": str(e),
                    "locations": [],
                    "path": []
                }]
            }
        except Exception as e:
            # Unexpected errors should bubble as HTTP 500
            raise
    
    def _parse_query(self, query: str) -> List[str]:
        """
        Parse simple GraphQL-like query to extract field paths.
        Supports basic dot notation: user.profile.name
        """
        # Simple implementation - extract field names
        # In production, use a proper GraphQL parser
        selectors = []
        lines = query.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and '{' not in line and '}' not in line:
                selectors.append(line.strip())
        return selectors
    
    def _select_fields(self, data: Dict[str, Any], selectors: List[str]) -> Dict[str, Any]:
        """
        Select specified fields from data using dot notation.
        """
        result = {}
        for selector in selectors:
            value = self._get_nested_value(data, selector)
            self._set_nested_value(result, selector, value)
        return result
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any):
        """Set value in nested dictionary using dot notation."""
        keys = path.split('.')
        current = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
    
    def transform_data(self, source_data: Dict[str, Any], target_data: Dict[str, Any], 
                       mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Transform data using field mappings.
        
        Args:
            source_data: Source data dictionary
            target_data: Target data dictionary (will be modified)
            mappings: List of mapping definitions
            
        Returns:
            TransformResponse with transformed data and errors
        """
        errors = []
        
        for mapping in mappings:
            try:
                source_field = mapping.get("source_field")
                target_field = mapping.get("target_field")
                transformation = mapping.get("transformation")
                
                if not source_field or not target_field:
                    errors.append({
                        "mapping": mapping,
                        "error": "Missing source_field or target_field"
                    })
                    continue
                
                # Get source value
                source_value = self._get_nested_value(source_data, source_field)
                
                # Apply transformation if specified
                if transformation:
                    try:
                        source_value = self._apply_transformation(source_value, transformation)
                    except Exception as e:
                        errors.append({
                            "mapping": mapping,
                            "error": f"Transformation failed: {str(e)}"
                        })
                        continue
                
                # Set target value
                self._set_nested_value(target_data, target_field, source_value)
                
            except Exception as e:
                errors.append({
                    "mapping": mapping,
                    "error": str(e)
                })
        
        return {
            "transformed_data": target_data,
            "errors": errors,
            "mappings_applied": len(mappings) - len(errors),
            "mappings_failed": len(errors)
        }
    
    def _apply_transformation(self, value: Any, transformation: str) -> Any:
        """
        Apply inline transformation to value.
        Supports: uppercase, lowercase, trim, int, float, bool
        """
        if value is None:
            return None
        
        trans = transformation.lower().strip()
        
        if trans == "uppercase":
            return str(value).upper()
        elif trans == "lowercase":
            return str(value).lower()
        elif trans == "trim":
            return str(value).strip()
        elif trans == "int":
            return int(value)
        elif trans == "float":
            return float(value)
        elif trans == "bool":
            return bool(value)
        else:
            raise ValueError(f"Unknown transformation: {transformation}")
