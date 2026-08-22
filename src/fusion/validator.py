"""Schema Validator for Music IR v0.1.

Strictly validates Music IR dictionaries against `schemas/music-ir-v0.1.schema.json`.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ValidationError(Exception):
    """Raised when Music IR validation fails against schema."""
    pass


# Cache loaded schema in memory
_CACHED_SCHEMA: Optional[Dict[str, Any]] = None


def load_schema(schema_path: Optional[str] = None) -> Dict[str, Any]:
    """Load JSON Schema from disk or cache."""
    global _CACHED_SCHEMA
    if _CACHED_SCHEMA is not None and schema_path is None:
        return _CACHED_SCHEMA

    target_path = Path(schema_path) if schema_path else Path(__file__).parent.parent.parent / "schemas" / "music-ir-v0.1.schema.json"
    with open(target_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    if schema_path is None:
        _CACHED_SCHEMA = schema
    return schema


def _check_type(val: Any, expected_type: Union[str, List[str]], path: str) -> None:
    """Validate python primitive against JSON Schema type(s)."""
    type_map = {
        "object": dict,
        "array": list,
        "string": str,
        "number": (int, float),
        "boolean": bool,
        "null": type(None),
    }

    if isinstance(expected_type, list):
        valid = False
        for t in expected_type:
            if t == "null" and val is None:
                valid = True
                break
            elif t in type_map and isinstance(val, type_map[t]) and not (t != "boolean" and isinstance(val, bool)):
                valid = True
                break
        if not valid:
            raise ValidationError(f"Type mismatch at '{path}': expected one of {expected_type}, got {type(val).__name__} ({repr(val)})")
        return

    if expected_type == "null":
        if val is not None:
            raise ValidationError(f"Type mismatch at '{path}': expected null, got {type(val).__name__}")
        return

    expected_cls = type_map.get(expected_type)
    if expected_cls is None:
        return

    # In Python, bool is a subclass of int, so handle specifically
    if expected_type == "number" and isinstance(val, bool):
        raise ValidationError(f"Type mismatch at '{path}': expected number, got bool")
    if expected_type != "boolean" and isinstance(val, bool):
        raise ValidationError(f"Type mismatch at '{path}': expected {expected_type}, got bool")

    if not isinstance(val, expected_cls):
        raise ValidationError(f"Type mismatch at '{path}': expected {expected_type}, got {type(val).__name__}")


def _validate_node(instance: Any, schema_node: Dict[str, Any], path: str = "$") -> None:
    """Recursively validate instance against schema sub-node."""
    # 1. Type validation
    if "type" in schema_node:
        _check_type(instance, schema_node["type"], path)

    # 2. Const validation
    if "const" in schema_node:
        if instance != schema_node["const"]:
            raise ValidationError(f"Const mismatch at '{path}': expected '{schema_node['const']}', got '{instance}'")

    # 3. Enum validation
    if "enum" in schema_node:
        if instance not in schema_node["enum"]:
            raise ValidationError(f"Enum mismatch at '{path}': '{instance}' not in {schema_node['enum']}")

    # 4. Minimum validation
    if "minimum" in schema_node:
        if isinstance(instance, (int, float)) and instance < schema_node["minimum"]:
            raise ValidationError(f"Value at '{path}' ({instance}) is less than minimum {schema_node['minimum']}")

    # 5. Object validation
    if isinstance(instance, dict):
        required_keys = schema_node.get("required", [])
        for req in required_keys:
            if req not in instance:
                raise ValidationError(f"Missing required property '{req}' at '{path}'")

        properties = schema_node.get("properties", {})
        for key, val in instance.items():
            if key in properties:
                _validate_node(val, properties[key], f"{path}.{key}")

    # 6. Array validation
    if isinstance(instance, list) and "items" in schema_node:
        item_schema = schema_node["items"]
        for idx, item in enumerate(instance):
            _validate_node(item, item_schema, f"{path}[{idx}]")


def validate_music_ir(data: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> None:
    """Validate Music IR dictionary against schema rules."""
    if not isinstance(data, dict):
        raise ValidationError("Music IR root must be a JSON object")

    if schema is None:
        schema = load_schema()

    _validate_node(data, schema, "$")
