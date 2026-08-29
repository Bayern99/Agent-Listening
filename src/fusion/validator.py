"""JSON Schema validation for Music IR v0.1."""

import json
from math import isclose
from pathlib import Path
from typing import Any, Dict, Optional

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError


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


def validate_music_ir(data: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> None:
    """Validate a Music IR dictionary against Draft 2020-12."""
    schema = schema or load_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    try:
        validator.validate(data)
    except JsonSchemaValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path) or "$"
        raise ValidationError(f"{location}: {exc.message}") from exc

    duration = data["track"]["duration_s"]
    for field in ("beats_s", "downbeats_s"):
        timestamps = data["structure"][field]
        if timestamps != sorted(timestamps) or any(timestamp > duration + 1e-3 for timestamp in timestamps):
            raise ValidationError(f"structure.{field}: timestamps must be sorted within track duration")

    sections = data["structure"]["sections"]
    previous_end = 0.0
    for index, section in enumerate(sections):
        start, end = section["start_s"], section["end_s"]
        if start >= end or not isclose(start, previous_end, abs_tol=1e-3) or end > duration + 1e-3:
            raise ValidationError(f"structure.sections.{index}: sections must be continuous, ordered, and within duration")
        previous_end = end
    if sections and not isclose(previous_end, duration, abs_tol=1e-3):
        raise ValidationError("structure.sections: sections must cover the full track duration")
