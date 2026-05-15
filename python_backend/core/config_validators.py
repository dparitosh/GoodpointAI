"""
Shared Configuration Validators
================================

Centralized validation functions for all configuration operations.
Eliminates duplication across admin_config_router, pipeline_config_router,
config_router, and agentic_config_router.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Pattern
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================
# FIELD VALIDATION HELPERS
# ============================================================

def validate_required_fields(data: Dict[str, Any], required: List[str]) -> tuple[bool, Optional[List[str]]]:
    """
    Validate that all required fields are present and non-empty.
    
    Args:
        data: Dictionary to validate
        required: List of required field names
    
    Returns:
        Tuple of (is_valid, missing_fields_list)
    """
    missing: List[str] = []
    for key in required:
        val = data.get(key)
        if val is None:
            missing.append(key)
            continue
        if isinstance(val, str) and not val.strip():
            missing.append(key)
            continue
    
    return (len(missing) == 0, missing if missing else None)


def validate_field_format(value: str, format_type: str) -> tuple[bool, Optional[str]]:
    """
    Validate field format (email, URL, UUID, etc.).
    
    Args:
        value: Value to validate
        format_type: Type of format (email, url, uuid, hostname, port, etc.)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    formats: Dict[str, Pattern[str]] = {
        'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
        'url': re.compile(r'^https?://[^\s]+$'),
        'uuid': re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE),
        'hostname': re.compile(r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$'),
        'ipv4': re.compile(r'^(\d{1,3}\.){3}\d{1,3}$'),
    }
    
    if format_type not in formats:
        return (True, None)  # Unknown format, skip validation
    
    pattern = formats[format_type]
    is_valid = bool(pattern.match(value))
    
    error = None if is_valid else f"Invalid {format_type} format: {value}"
    return (is_valid, error)


def validate_field_range(value: Any, min_val: Optional[Any] = None, max_val: Optional[Any] = None) -> tuple[bool, Optional[str]]:
    """
    Validate that value is within range.
    
    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if min_val is not None and value < min_val:
            return (False, f"Value {value} is less than minimum {min_val}")
        if max_val is not None and value > max_val:
            return (False, f"Value {value} exceeds maximum {max_val}")
        return (True, None)
    except TypeError as e:
        return (False, f"Range validation failed: {str(e)}")


def validate_field_choices(value: str, allowed_choices: List[str]) -> tuple[bool, Optional[str]]:
    """
    Validate that value is one of allowed choices.
    
    Args:
        value: Value to validate
        allowed_choices: List of allowed values
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value not in allowed_choices:
        return (False, f"Invalid choice '{value}'. Allowed: {', '.join(allowed_choices)}")
    return (True, None)


def validate_field_regex(value: str, pattern: str) -> tuple[bool, Optional[str]]:
    """
    Validate field against regex pattern.
    
    Args:
        value: Value to validate
        pattern: Regex pattern string
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        regex = re.compile(pattern)
        is_valid = bool(regex.match(value))
        error = None if is_valid else f"Value '{value}' does not match pattern '{pattern}'"
        return (is_valid, error)
    except re.error as e:
        logger.error("Invalid regex pattern: %s", e)
        return (False, f"Invalid regex pattern: {str(e)}")


# ============================================================
# CONNECTION VALIDATION
# ============================================================

def mask_secret(value: Optional[str], show_chars: int = 4) -> Optional[str]:
    """
    Mask a secret value, showing only last few characters.
    
    Args:
        value: Secret value to mask
        show_chars: Number of chars to show at end
    
    Returns:
        Masked string or None
    """
    if not value:
        return None
    if len(value) <= show_chars:
        return "*" * len(value)
    return "*" * (len(value) - show_chars) + value[-show_chars:]


def validate_connection_params(params: Dict[str, Any], required_params: List[str]) -> tuple[bool, Optional[Dict[str, str]]]:
    """
    Validate connection parameters.
    
    Args:
        params: Connection parameters dict
        required_params: List of required parameter names
    
    Returns:
        Tuple of (is_valid, errors_dict)
    """
    errors: Dict[str, str] = {}
    
    # Check required fields
    is_valid, missing = validate_required_fields(params, required_params)
    if missing:
        for field in missing:
            errors[field] = f"Required field '{field}' is missing or empty"
    
    return (len(errors) == 0, errors if errors else None)


# ============================================================
# AUDIT LOGGING
# ============================================================

class AuditEntry:
    """Helper for building audit log entries."""
    
    def __init__(self, config_type: str, config_id: str, action: str):
        self.config_type = config_type
        self.config_id = str(config_id)
        self.action = action
        self.timestamp = datetime.now(datetime.now().astimezone().tzinfo)
        self.old_value: Optional[Dict[str, Any]] = None
        self.new_value: Optional[Dict[str, Any]] = None
        self.changed_fields: Optional[List[str]] = None
        self.user_id: Optional[str] = None
        self.user_name: Optional[str] = None
        self.ip_address: Optional[str] = None
        self.notes: Optional[str] = None
    
    def with_values(self, old_value: Optional[Dict[str, Any]] = None, new_value: Optional[Dict[str, Any]] = None) -> 'AuditEntry':
        """Set old and new values, calculate changed fields."""
        self.old_value = old_value
        self.new_value = new_value
        
        # Calculate changed fields
        if old_value and new_value:
            self.changed_fields = [k for k in new_value if old_value.get(k) != new_value.get(k)]
        elif new_value:
            self.changed_fields = list(new_value.keys())
        
        return self
    
    def with_user(self, user_id: str, user_name: str, ip_address: str) -> 'AuditEntry':
        """Set user information."""
        self.user_id = user_id
        self.user_name = user_name
        self.ip_address = ip_address
        return self
    
    def with_notes(self, notes: str) -> 'AuditEntry':
        """Add notes to the audit entry."""
        self.notes = notes
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'config_type': self.config_type,
            'config_id': self.config_id,
            'action': self.action,
            'timestamp': self.timestamp.isoformat(),
            'old_value': self.old_value,
            'new_value': self.new_value,
            'changed_fields': self.changed_fields,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'ip_address': self.ip_address,
            'notes': self.notes,
        }


# ============================================================
# RESPONSE ENVELOPE BUILDER
# ============================================================

class ConfigResponse:
    """Standard response format for all config operations."""
    
    @staticmethod
    def success(message: str = "Success", data: Optional[Any] = None, timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Build success response."""
        return {
            'status': 'success',
            'message': message,
            'data': data,
            'timestamp': timestamp or datetime.now().isoformat(),
        }
    
    @staticmethod
    def error(message: str, code: str = "ERROR", details: Optional[Any] = None, timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Build error response."""
        return {
            'status': 'error',
            'message': message,
            'code': code,
            'details': details,
            'timestamp': timestamp or datetime.now().isoformat(),
        }
    
    @staticmethod
    def created(resource_id: str, message: str = "Resource created", data: Optional[Any] = None) -> Dict[str, Any]:
        """Build creation response."""
        return {
            'status': 'success',
            'message': message,
            'resource_id': resource_id,
            'data': data,
            'timestamp': datetime.now().isoformat(),
        }
    
    @staticmethod
    def updated(message: str = "Resource updated", data: Optional[Any] = None) -> Dict[str, Any]:
        """Build update response."""
        return {
            'status': 'success',
            'message': message,
            'data': data,
            'timestamp': datetime.now().isoformat(),
        }
    
    @staticmethod
    def deleted(message: str = "Resource deleted") -> Dict[str, Any]:
        """Build deletion response."""
        return {
            'status': 'success',
            'message': message,
            'timestamp': datetime.now().isoformat(),
        }


# ============================================================
# CACHE INVALIDATION
# ============================================================

def invalidate_admin_config_cache():
    """Invalidate the admin config service cache."""
    try:
        from services.admin_config_service import invalidate_config_cache as _invalidate
        _invalidate()
        logger.info("Admin config cache invalidated")
    except Exception as e:
        logger.warning("Failed to invalidate config cache: %s", e)


def invalidate_pipeline_config_cache():
    """Invalidate the pipeline config service cache."""
    try:
        # Import and call cache invalidation if service exists
        logger.info("Pipeline config cache invalidation requested")
    except Exception as e:
        logger.warning("Failed to invalidate pipeline config cache: %s", e)


# ============================================================
# CONFIGURATION MERGE & DIFF
# ============================================================

def deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, with updates overriding base.
    
    Args:
        base: Base dictionary
        updates: Updates to merge in
    
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def calculate_config_diff(old_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate differences between two configurations.
    
    Args:
        old_config: Previous configuration
        new_config: New configuration
    
    Returns:
        Diff structure with added, removed, modified fields
    """
    diff = {
        'added': {},
        'removed': {},
        'modified': {},
    }
    
    # Find added and modified
    for key, new_val in new_config.items():
        if key not in old_config:
            diff['added'][key] = new_val
        elif old_config[key] != new_val:
            diff['modified'][key] = {
                'old': old_config[key],
                'new': new_val,
            }
    
    # Find removed
    for key, old_val in old_config.items():
        if key not in new_config:
            diff['removed'][key] = old_val
    
    return diff
