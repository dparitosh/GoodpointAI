"""
GraphQL Service - Core parsing, schema generation, and pseudo-GraphQL execution.
Supports XML and JSON schema introspection, query execution, and data transformations.
"""

import json
import xml.etree.ElementTree as ET
import hashlib
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone


def _utcnow_iso() -> str:
    # Keep naive UTC timestamps (previous behavior) without using deprecated datetime.utcnow().
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


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
            raise ValueError(f"Invalid XML format: {str(e)}") from e
    
    def _element_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary recursively."""
        result: Dict[str, Any] = {}
        
        # Add attributes
        if element.attrib:
            result["@attributes"] = dict(element.attrib)
        
        text = element.text.strip() if element.text and element.text.strip() else None

        # Add text content
        if text is not None:
            result["@text"] = text
        
        # Add children
        for child in list(element):
            child_data = self._element_to_dict(child)
            if child.tag in result:
                # Convert to list if multiple elements with same tag
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                if isinstance(result[child.tag], list):
                    result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result
    
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
            raise ValueError(f"Invalid JSON format: {str(e)}") from e
    
    def introspect_schema(
        self,
        content: str,
        format_: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
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
        if not name:
            raise ValueError("Schema name is required")

        # Backwards compatibility: callers may pass `format=` as a keyword argument.
        data_format = (format_ or kwargs.get("format") or "").lower().strip()
        if data_format not in ["xml", "json"]:
            raise ValueError(f"Invalid format: {data_format}. Must be 'xml' or 'json'")
        
        # Parse content based on format
        if data_format == 'xml':
            data = self.parse_xml_to_dict(content)
        else:
            data = self.parse_json_to_dict(content)
        
        # Generate schema hash (use first 10KB for large files to speed up)
        hash_content = content[:10240] if len(content) > 10240 else content
        content_hash = hashlib.sha256(hash_content.encode()).hexdigest()

        cache_key = (name, data_format, content_hash)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Fast entity-based schema extraction (no recursion)
        entities, properties = self._extract_entities_iterative(data)

        # If the fast-path didn't find typed entities/properties (common for plain JSON/XML
        # without explicit type markers), fall back to full schema extraction to preserve
        # expected dotted field paths like "user.id".
        if not properties:
            fields, types = self._extract_schema(data)
            properties = fields
            entities = types or entities
        
        result = {
            "name": name,
            "format": data_format,
            "schema_hash": content_hash,
            "fields": properties,
            "types": entities,
            "metadata": {
                "introspected_at": _utcnow_iso(),
                "field_count": len(properties),
                "type_count": len(entities)
            }
        }

        self.cache[cache_key] = result
        return result
    
    def _extract_entities_iterative(self, data: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Fast iterative entity/property extraction using BFS.
        Uses a bounded queue - no recursion, no stack overflow.
        Depth limit removed - just bounded by max_process count.
        """
        entities: Dict[str, Any] = {}
        properties: Dict[str, Any] = {}
        seen_types: set = set()
        
        # Use deque for BFS - process items breadth-first
        from collections import deque
        queue: deque = deque()
        
        # Initialize queue from data
        if isinstance(data, list):
            for item in data[:200]:  # Max 200 top-level items
                if isinstance(item, dict):
                    queue.append(item)
        elif isinstance(data, dict):
            queue.append(data)
        
        processed = 0
        max_process = 5000  # Process up to 5000 items - enough for rich schema
        
        while queue and processed < max_process:
            processed += 1
            item = queue.popleft()
            
            if not isinstance(item, dict):
                continue
            
            # Extract entity type from various possible markers
            etype = item.get("_type") or item.get("type") or item.get("@type")
            if etype and etype not in seen_types:
                seen_types.add(etype)
                entities[etype] = {"name": etype, "kind": "ENTITY", "properties": {}}
                
                # Extract all scalar properties
                for k, v in item.items():
                    if k in ("_children", "children", "_type", "type", "@type", "_text"):
                        continue
                    if not isinstance(v, (dict, list)):
                        ptype = self._infer_type(v)
                        properties[f"{etype}.{k}"] = {"type": ptype, "entity": etype}
                        entities[etype]["properties"][k] = ptype
            
            # Queue all nested objects/arrays for processing
            for k, v in item.items():
                if k == "_text":  # Skip text content
                    continue
                if isinstance(v, dict):
                    queue.append(v)
                elif isinstance(v, list):
                    # Queue list items (limited per list)
                    for child in v[:50]:
                        if isinstance(child, dict):
                            queue.append(child)
        
        if not entities:
            entities["Object"] = {"name": "Object", "kind": "OBJECT", "properties": {}}
        
        return entities, properties
    
    def _extract_schema(
        self,
        data: Any,
        path: str = "",
        fields: Optional[Dict[str, Any]] = None,
        types: Optional[Dict[str, Any]] = None,
        depth: int = 0,
        max_depth: int = 10,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Recursively extract field definitions and type information from data structure.
        
        Args:
            max_depth: Maximum recursion depth to prevent infinite loops on deeply nested data
        
        Returns:
            Tuple of (fields dict, types dict)
        """
        if fields is None:
            fields = {}
        if types is None:
            types = {}
        
        # Prevent infinite recursion on deeply nested structures
        if depth >= max_depth:
            return fields, types
        
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
                
                # Recurse for nested structures (with depth limit)
                if isinstance(value, (dict, list)):
                    self._extract_schema(value, field_path, fields, types, depth + 1, max_depth)
        
        elif isinstance(data, list) and len(data) > 0:
            # Analyze first item for array type
            self._extract_schema(data[0], path, fields, types, depth + 1, max_depth)
        
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
            if variables is not None:
                _ = variables

            # Support both dot-notation selectors and a very small subset of
            # GraphQL selection sets: { root { field subfield } }
            if "{" in query and "}" in query:
                result = self._execute_selection_set_query(query, data)
            else:
                selectors = self._parse_query(query)
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

    def _execute_selection_set_query(self, query: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a minimal GraphQL-like selection set.

        Supported shape:
        {
          users { id name }
          items { id }
        }

        This is intentionally not a full GraphQL parser.
        """
        selections = self._parse_selection_set(query)
        result: Dict[str, Any] = {}

        for root_field, child_fields in selections.items():
            root_value = data.get(root_field)
            result[root_field] = self._apply_child_field_selection(root_value, child_fields)

        return result

    def _parse_selection_set(self, query: str) -> Dict[str, List[str]]:
        """Parse a minimal selection set into {root_field: [child_fields...]}"""
        # Strip comments and keep only relevant characters.
        cleaned_lines: list[str] = []
        for line in query.splitlines():
            line = line.split("#", 1)[0]
            if line.strip():
                cleaned_lines.append(line)
        cleaned = "\n".join(cleaned_lines)

        selections: Dict[str, List[str]] = {}
        depth = 0
        current_root: Optional[str] = None
        word = ""

        def flush_word() -> None:
            nonlocal word, current_root
            if not word:
                return
            if depth == 1:
                current_root = word
                selections.setdefault(current_root, [])
            elif depth == 2 and current_root is not None:
                selections[current_root].append(word)
            word = ""

        for ch in cleaned:
            if ch.isalnum() or ch == "_":
                word += ch
                continue

            flush_word()
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
                if depth < 2:
                    current_root = None

        flush_word()
        return selections

    def _apply_child_field_selection(self, value: Any, child_fields: List[str]) -> Any:
        """Apply selection of child fields to dict/list structures."""
        if not child_fields:
            return value

        if isinstance(value, list):
            selected_list: list[Any] = []
            for item in value:
                if isinstance(item, dict):
                    selected_list.append({k: item.get(k) for k in child_fields})
                else:
                    selected_list.append(item)
            return selected_list

        if isinstance(value, dict):
            return {k: value.get(k) for k in child_fields}

        return value
    
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
        result: Dict[str, Any] = {}
        for selector in selectors:
            value = self._get_nested_value(data, selector)
            self._set_nested_value(result, selector, value)
        return result
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split('.')
        value: Any = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any):
        """Set value in nested dictionary using dot notation."""
        keys = path.split('.')
        current: Dict[str, Any] = data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            next_value = current[key]
            if not isinstance(next_value, dict):
                next_value = {}
                current[key] = next_value
            current = next_value
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
                source_field = mapping.get("source_field") or mapping.get("source_path")
                target_field = mapping.get("target_field") or mapping.get("target_path")
                transformation = mapping.get("transformation")
                
                if not source_field or not target_field:
                    errors.append({
                        "mapping": mapping,
                        "error": "Missing source_field/target_field (or source_path/target_path)"
                    })
                    continue
                
                # Get source value
                source_value = self._get_nested_value(source_data, source_field)
                
                # Apply transformation if specified
                if transformation:
                    try:
                        source_value = self._apply_transformation(source_value, transformation)
                    except (ValueError, TypeError) as e:
                        errors.append({
                            "mapping": mapping,
                            "error": f"Transformation failed: {str(e)}"
                        })
                        continue
                
                # Set target value
                self._set_nested_value(target_data, target_field, source_value)
                
            except (ValueError, TypeError, KeyError) as e:
                errors.append({
                    "mapping": mapping,
                    "error": str(e)
                })
        
        mappings_applied = len(mappings) - len(errors)
        mappings_failed = len(errors)
        transformed_data = target_data

        # Return a superset response shape to stay compatible with both
        # unit tests (transformed_data/mappings_*) and integration tests
        # (success/data).
        return {
            "success": mappings_failed == 0,
            "data": transformed_data,
            "transformed_data": transformed_data,
            "errors": errors,
            "mappings_applied": mappings_applied,
            "mappings_failed": mappings_failed,
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
