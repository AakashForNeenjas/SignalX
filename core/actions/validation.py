from typing import Any, Dict

from core.action_schemas import ACTION_PARAM_SCHEMAS
from core.actions.params import parse_json


def validate_action_params(action: str, params: Any) -> tuple[bool, str]:
    schema = ACTION_PARAM_SCHEMAS.get(action)
    if not schema:
        return True, ""
    schema_type = schema.get("type", "none")

    if schema_type == "none":
        return True, ""
    if schema_type == "float":
        if params is None or str(params).strip() == "":
            return False, "Missing required numeric parameter"
        return True, ""
    if schema_type == "string":
        if params is None or str(params).strip() == "":
            return False, "Missing required string parameter"
        return True, ""
    if schema_type == "json":
        try:
            data = parse_json(params, default=None, strict=True)
        except Exception:
            return False, "Invalid JSON parameters"
        if not isinstance(data, dict):
            return False, "JSON parameters must be an object"
        ok, msg = _validate_schema(data, schema, path="")
        return ok, msg
    return True, ""


def _validate_schema(data: Dict[str, Any], schema: Dict[str, Any], path: str) -> tuple[bool, str]:
    required = schema.get("required", []) or []
    for key in required:
        if key not in data:
            return False, f"Missing required field: {path}{key}"
    fields = schema.get("fields", {}) or {}
    for key, sub_schema in fields.items():
        if key not in data:
            continue
        sub_type = sub_schema.get("type")
        if sub_type == "object":
            if not isinstance(data[key], dict):
                return False, f"Field {path}{key} must be an object"
            ok, msg = _validate_schema(data[key], sub_schema, path=f"{path}{key}.")
            if not ok:
                return ok, msg
    return True, ""
