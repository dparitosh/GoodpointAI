"""Utilities for converting Neo4j values to JSON-serializable Python types.

FastAPI/Pydantic v2 will raise if response models contain unknown types like
`neo4j.time.DateTime`. These helpers sanitize nested structures returned by the
Neo4j driver (node/relationship properties, records, etc.).
"""

from __future__ import annotations

from base64 import b64encode
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping


def _neo4j_temporal_to_native(value: Any) -> Any:
    """Best-effort conversion of Neo4j temporal types."""
    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        try:
            native = to_native()
            return native
        except Exception:
            return value
    return value


def to_jsonable(value: Any) -> Any:
    """Recursively convert *value* to JSON-serializable primitives.

    Strategy:
    - Preserve JSON primitives
    - Convert Neo4j temporal/spatial types to native/strings
    - Convert mappings/sequences recursively
    - Fallback to `str(value)`
    """

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # Common Python temporal types
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if isinstance(value, timedelta):
        # ISO 8601 duration formatting isn't standard in stdlib; keep it simple.
        return value.total_seconds()

    # Neo4j temporal types (e.g., neo4j.time.DateTime)
    value = _neo4j_temporal_to_native(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    # Bytes
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {"encoding": "base64", "data": b64encode(raw).decode("ascii")}

    # Mapping
    if isinstance(value, Mapping):
        return {str(k): to_jsonable(v) for k, v in value.items()}

    # Sequence / Set (but not str/bytes which are handled above)
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]

    # Neo4j spatial Point has x/y(/z) and srid
    srid = getattr(value, "srid", None)
    x = getattr(value, "x", None)
    y = getattr(value, "y", None)
    if srid is not None and x is not None and y is not None:
        payload = {"srid": srid, "x": x, "y": y}
        z = getattr(value, "z", None)
        if z is not None:
            payload["z"] = z
        return payload

    # Neo4j Node/Relationship and similar may be castable to dict
    try:
        as_dict = dict(value)  # type: ignore[arg-type]
        # Avoid treating plain iterables like list of pairs incorrectly.
        if as_dict and isinstance(as_dict, dict):
            return to_jsonable(as_dict)
    except Exception:
        pass

    # Pydantic models (v2)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return to_jsonable(model_dump())
        except Exception:
            pass

    # Fallback
    return str(value)


def sanitize_properties(properties: Any) -> dict[str, Any]:
    """Convert a properties mapping to a JSON-serializable dict."""
    if properties is None:
        return {}
    if isinstance(properties, Mapping):
        return to_jsonable(properties)
    # Best effort if the caller passed a Neo4j object
    try:
        return to_jsonable(dict(properties))  # type: ignore[arg-type]
    except Exception:
        return {"value": to_jsonable(properties)}
